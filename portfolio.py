# =============================================================
# portfolio.py — Gestor de cartera cripto con SQLite
# =============================================================

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import Optional

import aiohttp
import pandas as pd
import numpy as np

logger = logging.getLogger("tokomagraf_portfolio")

DECIMAL_PRECISION = Decimal("0.01")

# ── Rutas ───────────────────────────────────────────────────

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
DB_PATH = os.path.join(DATA_DIR, "tokomagraf.db")


# ── CoinGecko URLs ──────────────────────────────────────────

COINGECKO_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
COINGECKO_MARKET_URL = "https://api.coingecko.com/api/v3/coins/bitcoin?localization=false&tickers=false&community_data=false&developer_data=false&sparkline=false"


# ═════════════════════════════════════════════════════════════
#  Modelos de datos
# ═════════════════════════════════════════════════════════════

@dataclass
class Trade:
    id: int
    type: str  # 'buy' | 'sell'
    asset: str  # 'BTC' | 'USDC'
    amount: Decimal
    price: Decimal
    fee: Decimal
    notes: str
    created_at: str


@dataclass
class PortfolioData:
    """Todos los datos calculados de la cartera para el dashboard."""
    # Balances
    btc_balance: Decimal
    usdc_balance: Decimal
    total_invested: Decimal

    # Precio BTC desde CoinGecko
    btc_price: Decimal
    btc_price_change_24h: Optional[float]

    # Valor y rentabilidad
    portfolio_value: Decimal
    total_pnl: Decimal
    total_pnl_pct: float

    # Precio medio y objetivo
    avg_btc_price: Optional[Decimal]
    target_price: Optional[Decimal]
    target_pct: float
    progress_to_target: Optional[float]  # % del camino al objetivo

    # Beneficios
    daily_profit: Optional[Decimal]
    monthly_profit: Optional[Decimal]

    # Rentabilidad anualizada
    annualized_return: Optional[float]

    # Recomendación
    recommendation: str
    recommendation_explanation: str

    # Metadata
    first_trade_date: Optional[str]
    trade_count: int
    updated_at: str


@dataclass
class AssetPrice:
    price_usd: Decimal
    updated_at: datetime


@dataclass
class AssetPriceDetail:
    price_usd: Decimal
    change_24h_pct: Optional[float]
    high_24h: Optional[Decimal]
    low_24h: Optional[Decimal]
    updated_at: datetime


# ═════════════════════════════════════════════════════════════
#  Base de datos — Inicialización
# ═════════════════════════════════════════════════════════════

def _get_conn() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Crea tablas e inserta config por defecto si no existen."""
    conn = _get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('buy', 'sell')),
                asset TEXT NOT NULL CHECK(asset IN ('BTC', 'USDC', 'USDT')),
                amount REAL NOT NULL CHECK(amount > 0),
                price REAL NOT NULL CHECK(price > 0),
                fee REAL NOT NULL DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                total_value REAL NOT NULL,
                btc_balance REAL NOT NULL,
                usdc_balance REAL NOT NULL,
                total_invested REAL NOT NULL,
                btc_price REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('price_above', 'price_below', 'profit_target', 'loss_limit')),
                target_value REAL NOT NULL,
                asset TEXT NOT NULL DEFAULT 'BTC',
                note TEXT DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                triggered INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                triggered_at TEXT
            );

            CREATE TABLE IF NOT EXISTS imported_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                platform TEXT NOT NULL,
                trade_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS chat_ids (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL UNIQUE,
                first_name TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        conn.commit()

        # Config por defecto
        defaults = {
            "target_pct": "100",  # objetivo: +100% del precio medio
            "auto_snapshot": "1",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                (key, value),
            )
        conn.commit()
        logger.info("✅ Base de datos inicializada: %s", DB_PATH)
    except Exception as e:
        logger.error("Error inicializando DB: %s", e)
        raise
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════
#  Config
# ═════════════════════════════════════════════════════════════

def get_config(key: str, default: str = "") -> str:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_config(key: str, value: str) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════
#  Trades — Registro
# ═════════════════════════════════════════════════════════════

def register_trade(
    trade_type: str,
    asset: str,
    amount: Decimal,
    price: Decimal,
    fee: Decimal = Decimal("0"),
    notes: str = "",
) -> Optional[int]:
    """Registra un trade (compra o venta). Retorna el ID."""
    asset = asset.upper()
    if asset not in ("BTC", "USDC", "USDT"):
        logger.warning("Asset no soportado: %s", asset)
        return None
    if trade_type not in ("buy", "sell"):
        logger.warning("Tipo inválido: %s", trade_type)
        return None

    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO trades (type, asset, amount, price, fee, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (trade_type, asset, float(amount), float(price), float(fee), notes),
        )
        conn.commit()
        trade_id = cur.lastrowid
        logger.info(
            "✅ Trade #%s: %s %.6f %s @ $%.2f (fee: $%.2f)",
            trade_id, trade_type, float(amount), asset, float(price), float(fee),
        )
        return trade_id
    except Exception as e:
        logger.error("Error registrando trade: %s", e)
        return None
    finally:
        conn.close()


def get_recent_trades(limit: int = 20) -> list[Trade]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            Trade(
                id=r["id"],
                type=r["type"],
                asset=r["asset"],
                amount=Decimal(str(r["amount"])),
                price=Decimal(str(r["price"])),
                fee=Decimal(str(r["fee"])),
                notes=r["notes"] or "",
                created_at=r["created_at"],
            )
            for r in rows
        ]
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════
#  Cálculos de cartera
# ═════════════════════════════════════════════════════════════

def _sum_trades(asset: str, trade_type: str) -> Decimal:
    """Suma el amount de trades con filtro."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM trades WHERE asset = ? AND type = ?",
            (asset, trade_type),
        ).fetchone()
        return Decimal(str(row["total"]))
    finally:
        conn.close()


def _weighted_avg_price(asset: str) -> Optional[Decimal]:
    """Precio promedio ponderado de compras de un activo."""
    conn = _get_conn()
    try:
        row = conn.execute(
            """SELECT COALESCE(SUM(amount), 0) AS total_amount,
                       COALESCE(SUM(amount * price), 0) AS total_cost
                FROM trades WHERE asset = ? AND type = 'buy'""",
            (asset,),
        ).fetchone()
        total_amount = Decimal(str(row["total_amount"]))
        total_cost = Decimal(str(row["total_cost"]))
        if total_amount == 0:
            return None
        return (total_cost / total_amount).quantize(DECIMAL_PRECISION)
    finally:
        conn.close()


def get_btc_balance() -> Decimal:
    """BTC total = compras - ventas."""
    bought = _sum_trades("BTC", "buy")
    sold = _sum_trades("BTC", "sell")
    return (bought - sold).quantize(Decimal("0.00000001"))


def get_usdc_balance() -> Decimal:
    """USDC total = compras - ventas."""
    bought = _sum_trades("USDC", "buy")
    sold = _sum_trades("USDC", "sell")
    return (bought - sold).quantize(DECIMAL_PRECISION)


def get_usdt_balance() -> Decimal:
    """USDT total = compras - ventas."""
    bought = _sum_trades("USDT", "buy")
    sold = _sum_trades("USDT", "sell")
    return (bought - sold).quantize(DECIMAL_PRECISION)


def get_asset_balance(asset: str) -> Decimal:
    """Obtiene el balance de cualquier asset soportado."""
    asset = asset.upper()
    if asset == "BTC":
        return get_btc_balance()
    elif asset == "USDC":
        return get_usdc_balance()
    elif asset == "USDT":
        return get_usdt_balance()
    return Decimal("0")


def get_total_invested() -> Decimal:
    """Capital total invertido = suma de (amount * price + fee) de todas las compras."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount * price + fee), 0) AS total FROM trades WHERE type = 'buy'",
        ).fetchone()
        return Decimal(str(row["total"])).quantize(DECIMAL_PRECISION)
    finally:
        conn.close()


def get_avg_btc_price() -> Optional[Decimal]:
    return _weighted_avg_price("BTC")


def get_first_trade_date() -> Optional[str]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT created_at FROM trades ORDER BY created_at ASC LIMIT 1",
        ).fetchone()
        return row["created_at"] if row else None
    finally:
        conn.close()


def get_trade_count() -> int:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) AS cnt FROM trades").fetchone()
        return row["cnt"]
    finally:
        conn.close()


# ═════════════════════════════════════════════════════════════
#  Snapshots — Beneficio diario / mensual
# ═════════════════════════════════════════════════════════════

def save_snapshot(
    total_value: Decimal,
    btc_balance: Decimal,
    usdc_balance: Decimal,
    total_invested: Decimal,
    btc_price: Decimal,
) -> None:
    """Guarda un snapshot diario de la cartera (solo si no existe para hoy)."""
    today = date.today().isoformat()
    conn = _get_conn()
    try:
        existing = conn.execute(
            "SELECT id FROM snapshots WHERE date = ?", (today,),
        ).fetchone()
        if existing:
            return  # ya se guardó hoy
        conn.execute(
            """INSERT INTO snapshots (date, total_value, btc_balance, usdc_balance, total_invested, btc_price)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (today, float(total_value), float(btc_balance), float(usdc_balance),
             float(total_invested), float(btc_price)),
        )
        conn.commit()
        logger.info("📸 Snapshot guardado: %s", today)
    except Exception as e:
        logger.warning("Error guardando snapshot: %s", e)
    finally:
        conn.close()


def get_snapshot(target_date: date) -> Optional[dict]:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM snapshots WHERE date = ?",
            (target_date.isoformat(),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_daily_profit(current_value: Decimal) -> Optional[Decimal]:
    """Beneficio del día = valor actual - valor del snapshot de ayer."""
    yesterday = date.today() - timedelta(days=1)
    snap = get_snapshot(yesterday)
    if snap is None:
        # Intentar con el snapshot más reciente disponible
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM snapshots ORDER BY date DESC LIMIT 1",
            ).fetchone()
            snap = dict(row) if row else None
        finally:
            conn.close()
    if snap is None:
        return None
    prev_value = Decimal(str(snap["total_value"]))
    return (current_value - prev_value).quantize(DECIMAL_PRECISION)


def get_monthly_profit(current_value: Decimal) -> Optional[Decimal]:
    """Beneficio del mes = valor actual - valor del snapshot de hace ~30 días."""
    target = date.today() - timedelta(days=30)
    snap = get_snapshot(target)
    if snap is None:
        # Buscar el snapshot más cercano hacia atrás
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM snapshots WHERE date <= ? ORDER BY date DESC LIMIT 1",
                (target.isoformat(),),
            ).fetchone()
            snap = dict(row) if row else None
        finally:
            conn.close()
    if snap is None:
        return None
    prev_value = Decimal(str(snap["total_value"]))
    return (current_value - prev_value).quantize(DECIMAL_PRECISION)


# ═════════════════════════════════════════════════════════════
#  Recomendación
# ═════════════════════════════════════════════════════════════

def get_recommendation(pnl_pct: float) -> tuple[str, str]:
    """
    Reglas por rentabilidad:
    - P&L < -20%  → Compra parcial (oportunidad de DCA)
    - -20% <= P&L <= +50% → Mantener
    - P&L > +50% → Venta parcial (tomar ganancias)
    """
    if pnl_pct < -20:
        return (
            "🟢 Compra parcial",
            f"El mercado está en baja con una pérdida del **{pnl_pct:.1f}%**. "
            f"Si mantienes tu tesis de inversión a largo plazo, este puede ser "
            f"un buen momento para **promediar costo (DCA)** y reducir tu precio medio de compra.",
        )
    elif pnl_pct <= 50:
        return (
            "🟡 Mantener",
            f"La rentabilidad actual es del **{pnl_pct:.1f}%**, dentro del rango de estabilidad. "
            f" Sin señales claras de compra o venta según tus reglas. "
            f"Continúa monitoreando el mercado.",
        )
    else:
        return (
            "🔴 Venta parcial",
            f"Has alcanzado una ganancia del **{pnl_pct:.1f}%**, superando tu umbral del +50%. "
            f"Considera **vender una parte** para asegurar ganancias y reducir exposición al riesgo. "
            f"Puedes definir un nuevo objetivo para el remanente.",
        )


# ═════════════════════════════════════════════════════════════
#  Dashboard completo
# ═════════════════════════════════════════════════════════════

async def get_dashboard_data() -> Optional[PortfolioData]:
    """
    Calcula todos los datos de la cartera y guarda snapshot diario.
    Retorna None si no se puede obtener el precio de BTC.
    """
    # 1. Precio BTC
    btc_price_data = await fetch_btc_price_detail()
    if not btc_price_data:
        # Fallback a precio simple
        simple = await fetch_btc_price()
        if not simple:
            return None
        btc_price = simple.price_usd
        btc_change = None
    else:
        btc_price = btc_price_data.price_usd
        btc_change = btc_price_data.change_24h_pct

    # 2. Balances
    btc_balance = get_btc_balance()
    usdc_balance = get_usdc_balance()
    total_invested = get_total_invested()
    avg_btc_price = get_avg_btc_price()

    # 3. Valor de cartera
    btc_value = btc_balance * btc_price
    portfolio_value = (btc_value + usdc_balance).quantize(DECIMAL_PRECISION)

    # 4. P&L
    total_pnl = (portfolio_value - total_invested).quantize(DECIMAL_PRECISION)
    total_pnl_pct = float((total_pnl / total_invested * 100)) if total_invested > 0 else 0.0

    # 5. Precio objetivo
    target_pct = float(get_config("target_pct", "100"))
    target_price = (
        (avg_btc_price * (1 + target_pct / 100)).quantize(DECIMAL_PRECISION)
        if avg_btc_price else None
    )

    # 6. Progreso hacia objetivo
    progress_to_target = None
    if avg_btc_price and target_price and target_price > avg_btc_price:
        diff = float(btc_price - avg_btc_price)
        total_diff = float(target_price - avg_btc_price)
        if total_diff > 0:
            progress_to_target = round((diff / total_diff) * 100, 1)

    # 7. Beneficios diario y mensual
    daily_profit = get_daily_profit(portfolio_value)
    monthly_profit = get_monthly_profit(portfolio_value)

    # 8. Rentabilidad anualizada
    first_trade_date_str = get_first_trade_date()
    annualized_return = None
    if first_trade_date_str and total_invested > 0 and total_pnl != 0:
        try:
            first_dt = datetime.fromisoformat(first_trade_date_str)
            days_elapsed = (datetime.now(timezone.utc) - first_dt).days
            if days_elapsed > 0:
                total_return = float(total_pnl / total_invested)
                annualized = (1 + total_return) ** (365 / days_elapsed) - 1
                annualized_return = round(annualized * 100, 2)
        except Exception:
            pass

    # 9. Recomendación
    recommendation, explanation = get_recommendation(total_pnl_pct)

    # 10. Metadata
    trade_count = get_trade_count()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # 11. Snapshot diario automático
    try:
        save_snapshot(portfolio_value, btc_balance, usdc_balance, total_invested, btc_price)
    except Exception as e:
        logger.warning("Error guardando snapshot automático: %s", e)

    return PortfolioData(
        btc_balance=btc_balance,
        usdc_balance=usdc_balance,
        total_invested=total_invested,
        btc_price=btc_price,
        btc_price_change_24h=btc_change,
        portfolio_value=portfolio_value,
        total_pnl=total_pnl,
        total_pnl_pct=round(total_pnl_pct, 2),
        avg_btc_price=avg_btc_price,
        target_price=target_price,
        target_pct=target_pct,
        progress_to_target=progress_to_target,
        daily_profit=daily_profit,
        monthly_profit=monthly_profit,
        annualized_return=annualized_return,
        recommendation=recommendation,
        recommendation_explanation=explanation,
        first_trade_date=first_trade_date_str,
        trade_count=trade_count,
        updated_at=now_str,
    )


# ═════════════════════════════════════════════════════════════
#  Precio BTC (CoinGecko) — funciones originales
# ═════════════════════════════════════════════════════════════

async def fetch_btc_price() -> Optional[AssetPrice]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(COINGECKO_PRICE_URL, timeout=10) as resp:
                if resp.status != 200:
                    logger.warning("CoinGecko respondió %s", resp.status)
                    return None
                data = await resp.json()
                usd_price = data.get("bitcoin", {}).get("usd")
                if usd_price is None:
                    return None
                price = Decimal(str(usd_price))
                return AssetPrice(
                    price_usd=price.quantize(DECIMAL_PRECISION),
                    updated_at=datetime.now(timezone.utc),
                )
    except Exception as e:
        logger.error("Error obteniendo precio BTC: %s", e)
        return None


async def fetch_btc_price_detail() -> Optional[AssetPriceDetail]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(COINGECKO_MARKET_URL, timeout=10) as resp:
                if resp.status != 200:
                    logger.warning("CoinGecko (detail) respondió %s", resp.status)
                    return None
                data = await resp.json()
                market_data = data.get("market_data", {})
                price = Decimal(str(market_data.get("current_price", {}).get("usd", 0)))
                change_pct = market_data.get("price_change_percentage_24h")
                high = market_data.get("high_24h", {}).get("usd")
                low = market_data.get("low_24h", {}).get("usd")

                return AssetPriceDetail(
                    price_usd=price.quantize(DECIMAL_PRECISION),
                    change_24h_pct=float(change_pct) if change_pct is not None else None,
                    high_24h=Decimal(str(high)).quantize(DECIMAL_PRECISION) if high else None,
                    low_24h=Decimal(str(low)).quantize(DECIMAL_PRECISION) if low else None,
                    updated_at=datetime.now(timezone.utc),
                )
    except Exception as e:
        logger.error("Error obteniendo detalle precio BTC: %s", e)
        return None


# ═════════════════════════════════════════════════════════════
#  Datos históricos para gráfica
# ═════════════════════════════════════════════════════════════

async def fetch_btc_chart_data(days: int = 7) -> Optional[list[tuple[datetime, float]]]:
    url = f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days={days}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    logger.warning("CoinGecko chart respondió %s", resp.status)
                    return None
                data = await resp.json()
                prices = data.get("prices", [])
                if not prices:
                    return None
                result = []
                for ts_ms, price in prices:
                    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                    result.append((dt, float(price)))
                return result
    except Exception as e:
        logger.error("Error obteniendo datos históricos BTC: %s", e)
        return None


# ── Generación de gráfica ──────────────────────────────────

def generate_btc_chart(
    chart_data: list[tuple[datetime, float]],
    days: int = 7,
) -> Optional[str]:
    import os
    import time as _time
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import FuncFormatter

    if not chart_data or len(chart_data) < 2:
        return None

    dates = [d for d, _ in chart_data]
    prices = [p for _, p in chart_data]

    current_price = prices[-1]
    min_price = min(prices)
    max_price = max(prices)
    change_pct = ((prices[-1] - prices[0]) / prices[0]) * 100
    is_up = change_pct >= 0

    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    btc_color = "#f7931a"
    green = "#10b981"
    red = "#ef4444"
    line_color = green if is_up else red
    text_color = "#e6edf3"
    grid_color = "#21262d"

    ax.plot(dates, prices, color=line_color, linewidth=2.5, zorder=5)
    ax.fill_between(dates, min_price, prices, color=line_color, alpha=0.1)

    ax.axhline(y=current_price, color=line_color, linewidth=1, linestyle="--", alpha=0.5)
    ax.annotate(
        f"${current_price:,.0f}",
        xy=(dates[-1], current_price),
        xytext=(10, 0),
        textcoords="offset points",
        color=line_color,
        fontsize=11,
        fontweight="bold",
        va="center",
    )

    ax.grid(axis="y", color=grid_color, linestyle="--", alpha=0.4)
    ax.grid(axis="x", color=grid_color, linestyle="--", alpha=0.15)
    ax.tick_params(colors=text_color, labelsize=10)

    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    locator = mdates.AutoDateLocator(minticks=4, maxticks=10)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    period_text = {1: "24h", 7: "7 días", 14: "14 días", 30: "30 días", 90: "90 días"}.get(days, f"{days} días")
    fig.suptitle(
        f"📊  BTC/USD — Últimos {period_text}",
        color=btc_color,
        fontsize=18,
        fontweight="bold",
        y=0.96,
    )

    metrics_text = (
        f"Precio: ${current_price:,.2f}\n"
        f"Máx: ${max_price:,.2f}\n"
        f"Mín: ${min_price:,.2f}\n"
        f"Cambio: {change_pct:+.2f}%"
    )
    props = dict(
        boxstyle="round,pad=0.6",
        facecolor="#161b22",
        edgecolor=btc_color,
        alpha=0.95,
    )
    ax.text(
        0.02, 0.97, metrics_text,
        transform=ax.transAxes,
        fontsize=10,
        color=text_color,
        verticalalignment="top",
        bbox=props,
        family="monospace",
    )

    chart_dir = "/tmp/tokomagraf"
    os.makedirs(chart_dir, exist_ok=True)
    unique_id = f"{days}d_{int(_time.time() * 1000)}"
    chart_path = os.path.join(chart_dir, f"btc_chart_{unique_id}.png")
    plt.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    logger.info("📊 Gráfica BTC generada: %s", chart_path)
    return chart_path


async def generate_btc_chart_async(days: int = 7) -> Optional[str]:
    import asyncio
    chart_data = await fetch_btc_chart_data(days)
    if not chart_data:
        return None
    return await asyncio.to_thread(generate_btc_chart, chart_data, days)


# ═════════════════════════════════════════════════════════════
#  Formateo
# ═════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════
#  Análisis Técnico
# ═════════════════════════════════════════════════════════════

@dataclass
class TechnicalAnalysisResult:
    trend: str
    rsi: Optional[float]
    rsi_signal: str
    macd_line: Optional[float]
    macd_signal: Optional[float]
    macd_histogram: Optional[float]
    macd_cross: str
    sma_50: Optional[float]
    sma_200: Optional[float]
    sma_50_distance_pct: Optional[float]
    sma_200_distance_pct: Optional[float]
    support: Optional[float]
    resistance: Optional[float]
    signal_strength: str
    overall_signal: str
    scenarios: dict


def _calculate_sma(values: list[float], period: int) -> list[Optional[float]]:
    """Calcula Simple Moving Average."""
    series = pd.Series(values)
    sma = series.rolling(window=period).mean()
    return [float(v) if not pd.isna(v) else None for v in sma]


def _calculate_rsi(values: list[float], period: int = 14) -> list[Optional[float]]:
    """Calcula RSI (Relative Strength Index)."""
    series = pd.Series(values)
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.finfo(float).eps)
    rsi = 100 - (100 / (1 + rs))
    return [float(v) if not pd.isna(v) else None for v in rsi]


def _calculate_macd(values: list[float]):
    """Calcula MACD, Signal Line e Histograma."""
    series = pd.Series(values)
    ema_12 = series.ewm(span=12, adjust=False).mean()
    ema_26 = series.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    return (
        [float(v) if not pd.isna(v) else None for v in macd_line],
        [float(v) if not pd.isna(v) else None for v in signal_line],
        [float(v) if not pd.isna(v) else None for v in histogram],
    )


def _calculate_support_resistance(data: list[float]) -> tuple[Optional[float], Optional[float]]:
    """Calcula niveles de soporte y resistencia usando máximos/mínimos locales."""
    if len(data) < 20:
        return None, None

    highs: list[float] = []
    lows: list[float] = []

    for i in range(5, len(data) - 5):
        if all(data[i] >= data[i-j] for j in range(1, 6)) and all(data[i] >= data[i+j] for j in range(1, 6)):
            highs.append(data[i])
        if all(data[i] <= data[i-j] for j in range(1, 6)) and all(data[i] <= data[i+j] for j in range(1, 6)):
            lows.append(data[i])

    if not highs or not lows:
        return None, None

    def cluster(values: list[float], threshold: float = 0.02) -> list[float]:
        if not values:
            return []
        vals = sorted(values)
        clusters = [[vals[0]]]
        for v in vals[1:]:
            if abs(v - clusters[-1][-1]) / max(clusters[-1][-1], 0.01) < threshold:
                clusters[-1].append(v)
            else:
                clusters.append([v])
        return [sum(c) / len(c) for c in clusters]

    resistance_levels = cluster(highs)
    support_levels = cluster(lows)

    if not resistance_levels or not support_levels:
        return None, None

    current_price = data[-1]
    above = [r for r in resistance_levels if r > current_price]
    resistance = min(above) if above else max(resistance_levels)
    below = [s for s in support_levels if s < current_price]
    support = max(below) if below else min(support_levels)

    return round(support, 2), round(resistance, 2)


def _generate_scenarios(
    current_price: float,
    rsi: Optional[float],
    trend: str,
    support: Optional[float],
    resistance: Optional[float],
    sma_50_pct: Optional[float],
    sma_200_pct: Optional[float],
) -> dict:
    """Genera escenarios probabilísticos basados en reglas técnicas."""
    scenarios = {
        'compra': {'probabilidad': 'baja', 'razon': ''},
        'venta': {'probabilidad': 'baja', 'razon': ''},
        'hold': {'probabilidad': 'alta', 'razon': 'Mercado sin señales claras. Se recomienda mantener la posición.'},
    }

    buy_weight = 0
    buy_reasons: list[str] = []

    if rsi is not None:
        if rsi < 30:
            buy_reasons.append(f'RSI en {rsi:.1f} (sobreventa).')
            buy_weight += 3
        elif rsi < 40:
            buy_reasons.append(f'RSI en {rsi:.1f} (cerca de sobreventa).')
            buy_weight += 1

    if support is not None and current_price <= support * 1.02:
        buy_reasons.append(f'Precio cerca de soporte (${support:,.2f}).')
        buy_weight += 2

    if sma_200_pct is not None and sma_200_pct < -10:
        buy_reasons.append(f'Precio {sma_200_pct:+.1f}% bajo SMA 200 (posible rebote).')
        buy_weight += 2

    if buy_reasons:
        prob = 'alta' if buy_weight >= 5 else 'media' if buy_weight >= 3 else 'baja'
        scenarios['compra'] = {'probabilidad': prob, 'razon': ' '.join(buy_reasons)}
        if prob in ('alta', 'media'):
            scenarios['hold']['probabilidad'] = 'baja'

    sell_weight = 0
    sell_reasons: list[str] = []

    if rsi is not None:
        if rsi > 70:
            sell_reasons.append(f'RSI en {rsi:.1f} (sobrecompra).')
            sell_weight += 3
        elif rsi > 60:
            sell_reasons.append(f'RSI en {rsi:.1f} (cerca de sobrecompra).')
            sell_weight += 1

    if resistance is not None and current_price >= resistance * 0.98:
        sell_reasons.append(f'Precio cerca de resistencia (${resistance:,.2f}).')
        sell_weight += 2

    if sma_50_pct is not None and sma_50_pct > 15:
        sell_reasons.append(f'Precio {sma_50_pct:+.1f}% sobre SMA 50 (posible corrección).')
        sell_weight += 2

    if sell_reasons:
        prob = 'alta' if sell_weight >= 5 else 'media' if sell_weight >= 3 else 'baja'
        scenarios['venta'] = {'probabilidad': prob, 'razon': ' '.join(sell_reasons)}
        if prob in ('alta', 'media'):
            scenarios['hold']['probabilidad'] = 'baja'

    return scenarios


async def calculate_technical_analysis() -> Optional[TechnicalAnalysisResult]:
    """
    Obtiene datos históricos de BTC y calcula indicadores técnicos.
    Retorna None si no hay suficientes datos.
    """
    # Necesitamos al menos 200 datos para SMA 200
    chart_data = await fetch_btc_chart_data(90)  # 90 días de datos horarios o diarios
    if not chart_data or len(chart_data) < 30:
        return None

    prices = [p for _, p in chart_data]
    current_price = prices[-1]

    # SMA
    sma_50_raw = _calculate_sma(prices, min(50, len(prices)))
    sma_200_raw = _calculate_sma(prices, min(200, len(prices)))
    sma_50 = sma_50_raw[-1] if sma_50_raw and sma_50_raw[-1] is not None else None
    sma_200 = sma_200_raw[-1] if sma_200_raw and sma_200_raw[-1] is not None else None

    # RSI
    rsi_raw = _calculate_rsi(prices, 14)
    rsi = rsi_raw[-1] if rsi_raw and rsi_raw[-1] is not None else None

    # MACD
    macd_line, macd_signal, macd_hist = _calculate_macd(prices)
    macd_l = macd_line[-1] if macd_line and macd_line[-1] is not None else None
    macd_s = macd_signal[-1] if macd_signal and macd_signal[-1] is not None else None
    macd_h = macd_hist[-1] if macd_hist and macd_hist[-1] is not None else None

    # MACD cross
    macd_cross = "none"
    if len(macd_line) >= 2 and len(macd_signal) >= 2:
        prev_macd = macd_line[-2] if macd_line[-2] is not None else 0
        prev_sig = macd_signal[-2] if macd_signal[-2] is not None else 0
        curr_macd = macd_l or 0
        curr_sig = macd_s or 0
        if prev_macd <= prev_sig and curr_macd > curr_sig:
            macd_cross = "alcista"
        elif prev_macd >= prev_sig and curr_macd < curr_sig:
            macd_cross = "bajista"

    # RSI signal
    rsi_signal = "neutral"
    if rsi is not None:
        if rsi >= 70:
            rsi_signal = "sobrecompra"
        elif rsi <= 30:
            rsi_signal = "sobreventa"
        elif rsi >= 60:
            rsi_signal = "neutral-alto"
        elif rsi <= 40:
            rsi_signal = "neutral-bajo"

    # Trend detection
    trend = "lateral"
    if sma_50 is not None and sma_200 is not None:
        if sma_50 > sma_200 * 1.03:
            trend = "alcista"
        elif sma_50 < sma_200 * 0.97:
            trend = "bajista"
        else:
            trend = "lateral"
    elif sma_50 is not None:
        if current_price > sma_50 * 1.05:
            trend = "alcista"
        elif current_price < sma_50 * 0.95:
            trend = "bajista"

    # Refinar con RSI
    if rsi is not None:
        if rsi > 70 and trend == "alcista":
            trend = "alcista ( posible agotamiento)"
        elif rsi < 30 and trend == "bajista":
            trend = "bajista (posible rebote)"

    # Support / Resistance
    support, resistance = _calculate_support_resistance(prices)

    # Distance to SMAs
    sma_50_dist = round(((current_price / sma_50) - 1) * 100, 2) if sma_50 else None
    sma_200_dist = round(((current_price / sma_200) - 1) * 100, 2) if sma_200 else None

    # Overall signal strength
    signals = 0
    total = 0

    if rsi is not None:
        total += 1
        if rsi < 40:
            signals += 1  # buy
        elif rsi > 60:
            signals -= 1  # sell

    if sma_50 and sma_200:
        total += 1
        if sma_50 > sma_200:
            signals += 1
        else:
            signals -= 1

    if macd_cross != "none":
        total += 1
        if macd_cross == "alcista":
            signals += 1
        else:
            signals -= 1

    if total == 0:
        overall = "neutral"
        strength = "baja"
    else:
        ratio = signals / total
        if ratio > 0.3:
            overall = "compra"
            strength = "alta" if ratio > 0.6 else "media"
        elif ratio < -0.3:
            overall = "venta"
            strength = "alta" if ratio < -0.6 else "media"
        else:
            overall = "neutral"
            strength = "baja"

    # Scenarios
    scenarios = _generate_scenarios(
        current_price=current_price,
        rsi=rsi,
        trend=trend,
        support=support,
        resistance=resistance,
        sma_50_pct=sma_50_dist,
        sma_200_pct=sma_200_dist,
    )

    return TechnicalAnalysisResult(
        trend=trend,
        rsi=rsi,
        rsi_signal=rsi_signal,
        macd_line=macd_l,
        macd_signal=macd_s,
        macd_histogram=macd_h,
        macd_cross=macd_cross,
        sma_50=sma_50,
        sma_200=sma_200,
        sma_50_distance_pct=sma_50_dist,
        sma_200_distance_pct=sma_200_dist,
        support=support,
        resistance=resistance,
        signal_strength=strength,
        overall_signal=overall,
        scenarios=scenarios,
    )


def format_analysis_text(analysis: TechnicalAnalysisResult) -> str:
    """Formatea el análisis técnico para mostrar en Telegram."""
    lines = ["📊 **Análisis Técnico BTC**\n"]

    arrow = {"alcista": "📈", "bajista": "📉", "lateral": "➡️"}
    trend_icon = ""
    for key, icon in arrow.items():
        if key in analysis.trend:
            trend_icon = icon
            break

    lines.append(f"{trend_icon} **Tendencia:** {analysis.trend.capitalize()}")
    lines.append(f"💪 **Señal general:** {analysis.overall_signal.upper()} ({analysis.signal_strength})\n")

    # SMA
    lines.append("**Medias Móviles:**")
    if analysis.sma_50:
        lines.append(f"  • SMA 50: ${analysis.sma_50:,.2f} ({analysis.sma_50_distance_pct:+.2f}%)")
    if analysis.sma_200:
        lines.append(f"  • SMA 200: ${analysis.sma_200:,.2f} ({analysis.sma_200_distance_pct:+.2f}%)")
    if analysis.sma_50 and analysis.sma_200:
        if analysis.sma_50 > analysis.sma_200:
            lines.append(f"  ✅ Golden Cross (SMA 50 > SMA 200)")
        else:
            lines.append(f"  ❌ Death Cross (SMA 50 < SMA 200)")
    lines.append("")

    # RSI
    if analysis.rsi is not None:
        rsi_icon = "🟢" if analysis.rsi < 40 else "🔴" if analysis.rsi > 60 else "🟡"
        lines.append(f"**RSI (14):** {rsi_icon} {analysis.rsi:.1f} — {analysis.rsi_signal}")

    # MACD
    if analysis.macd_line is not None:
        cross_icon = "✅" if analysis.macd_cross == "alcista" else "❌" if analysis.macd_cross == "bajista" else "➡️"
        lines.append(f"**MACD:** {cross_icon} Cruce {analysis.macd_cross}")
        if analysis.macd_histogram is not None:
            hist_icon = "📈" if analysis.macd_histogram > 0 else "📉"
            lines.append(f"  {hist_icon} Histograma: {analysis.macd_histogram:+.2f}")

    # Soporte / Resistencia
    lines.append("")
    lines.append("**Niveles Clave:**")
    if analysis.support:
        lines.append(f"  🛡️ Soporte: ${analysis.support:,.2f}")
    if analysis.resistance:
        lines.append(f"  🧱 Resistencia: ${analysis.resistance:,.2f}")

    # Escenarios probabilísticos
    lines.append("")
    lines.append("**Escenarios:**")
    emoji_prob = {"alta": "🔴", "media": "🟡", "baja": "🟢"}
    for scenario, data in analysis.scenarios.items():
        if data['probabilidad'] != 'baja' or data['razon']:
            prob_emoji = emoji_prob.get(data['probabilidad'], '⚪')
            icon = {"compra": "🟢", "venta": "🔴", "hold": "💤"}.get(scenario, "")
            lines.append(f"  {icon} **{scenario.capitalize()}:** {prob_emoji} {data['probabilidad'].upper()}")
            if data['razon']:
                lines.append(f"    _{data['razon']}_")

    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════
#  Simulador de Trades
# ═════════════════════════════════════════════════════════════

@dataclass
class SimulationResult:
    trade_type: str
    asset: str
    amount: Decimal
    price: Decimal
    fee: Decimal
    total: Decimal
    new_btc_balance: Decimal
    new_usdc_balance: Decimal
    new_avg_price: Optional[Decimal]
    portfolio_value_after: Decimal
    estimated_pnl: Optional[Decimal]
    estimated_pnl_pct: Optional[float]


def simulate_trade(
    trade_type: str,
    asset: str,
    amount: Decimal,
    price: Optional[Decimal] = None,
    fee: Decimal = Decimal("0"),
) -> Optional[SimulationResult]:
    """
    Simula una compra/venta sin ejecutarla.
    Si no se especifica precio, usa el precio actual de BTC o $1 para stablecoins.
    """
    asset = asset.upper()
    if asset not in ("BTC", "USDC", "USDT"):
        return None
    if amount <= 0 or fee < 0:
        return None

    current_btc = get_btc_balance()
    current_usdc = get_usdc_balance()
    avg_price = get_avg_btc_price()
    current_invested = get_total_invested()

    if trade_type == "buy":
        total = amount * price + fee if price else amount * Decimal("1.00") + fee
        if asset == "BTC":
            new_btc = current_btc + amount
            new_usdc_bal = current_usdc
            # Recalcular precio medio ponderado
            old_cost = (avg_price or Decimal("0")) * current_btc if avg_price else Decimal("0")
            new_cost = amount * price if price else amount * Decimal("1.00")
            total_cost = old_cost + new_cost
            new_avg = (total_cost / new_btc).quantize(DECIMAL_PRECISION) if new_btc > 0 else avg_price
            new_invested = current_invested + total
        else:
            new_btc = current_btc
            new_usdc_bal = current_usdc + amount
            new_avg = avg_price
            new_invested = current_invested + total

        btc_value = new_btc * (price or Decimal("1.00")) if asset == "BTC" else new_btc * Decimal("1.00")
        portfolio_value = (btc_value + new_usdc_bal).quantize(DECIMAL_PRECISION)
        est_pnl = (portfolio_value - new_invested).quantize(DECIMAL_PRECISION)
        est_pnl_pct = round(float(est_pnl / new_invested * 100), 2) if new_invested > 0 else 0.0

    else:  # sell
        if price:
            revenue = amount * price - fee
        else:
            revenue = amount * Decimal("1.00") - fee

        if asset == "BTC":
            new_btc = current_btc - amount
            new_usdc_bal = current_usdc + revenue
            new_avg = avg_price
            new_invested = current_invested
            btc_value = new_btc * (price or Decimal("1.00"))
            portfolio_value = (btc_value + new_usdc_bal).quantize(DECIMAL_PRECISION)
            cost_basis = amount * (avg_price or Decimal("0"))
            est_pnl = (revenue - cost_basis).quantize(DECIMAL_PRECISION)
            est_pnl_pct = round(float(est_pnl / cost_basis * 100), 2) if cost_basis > 0 else 0.0
        else:
            new_btc = current_btc
            new_usdc_bal = current_usdc - amount
            new_avg = avg_price
            new_invested = current_invested - revenue
            btc_value = new_btc * (price or Decimal("1.00"))
            portfolio_value = (btc_value + new_usdc_bal).quantize(DECIMAL_PRECISION)
            est_pnl = None
            est_pnl_pct = None

        if new_btc < 0 or new_usdc_bal < 0:
            return None  # Balance insuficiente

    return SimulationResult(
        trade_type=trade_type,
        asset=asset,
        amount=amount,
        price=price or Decimal("1.00"),
        fee=fee,
        total=total,
        new_btc_balance=new_btc,
        new_usdc_balance=new_usdc_bal or Decimal("0"),
        new_avg_price=new_avg,
        portfolio_value_after=portfolio_value,
        estimated_pnl=est_pnl,
        estimated_pnl_pct=est_pnl_pct,
    )


def format_simulation(sim: SimulationResult, trade_type_str: str) -> str:
    """Formatea el resultado de una simulación."""
    icon = "🟢" if trade_type_str == "compra" else "🔴"
    lines = [
        f"{icon} **Simulación de {trade_type_str.capitalize()}**\n",
        f"• {format_btc(sim.amount) if sim.asset == 'BTC' else format_usd(sim.amount)} **{sim.asset}**",
        f"• Precio: {format_usd(sim.price)}",
        f"• Fee: {format_usd(sim.fee)}",
        f"• {'Costo' if trade_type_str == 'compra' else 'Recibido'} total: {format_usd(sim.total)}",
        "",
        "**Resultado estimado:**",
        f"• Nuevo BTC: {format_btc(sim.new_btc_balance)}",
        f"• Nuevo USDC: {format_usd(sim.new_usdc_balance)}",
        f"• Nuevo precio medio: {format_usd(sim.new_avg_price) if sim.new_avg_price else '—'}",
        f"• Valor cartera después: {format_usd(sim.portfolio_value_after)}",
    ]

    if sim.estimated_pnl is not None:
        pnl_str = format_usd(sim.estimated_pnl)
        lines.append(f"• P&L estimado: {pnl_str}")
    if sim.estimated_pnl_pct is not None:
        lines.append(f"• Rentabilidad: {format_pct(sim.estimated_pnl_pct)}")

    lines.append("", "💡 Usá `/comprar` o `/vender` para ejecutar esta operación.")
    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════
#  Alertas de Precio
# ═════════════════════════════════════════════════════════════

@dataclass
class Alert:
    id: int
    type: str
    target_value: Decimal
    asset: str
    note: str
    active: bool
    triggered: bool
    created_at: str
    triggered_at: Optional[str]


def create_alert(
    alert_type: str,
    target_value: Decimal,
    asset: str = "BTC",
    note: str = "",
) -> Optional[int]:
    """Crea una alerta de precio o rentabilidad."""
    if alert_type not in ("price_above", "price_below", "profit_target", "loss_limit"):
        return None
    if target_value <= 0:
        return None

    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO alerts (type, target_value, asset, note)
               VALUES (?, ?, ?, ?)""",
            (alert_type, float(target_value), asset.upper(), note),
        )
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        logger.error("Error creando alerta: %s", e)
        return None
    finally:
        conn.close()


def get_active_alerts() -> list[Alert]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE active = 1 AND triggered = 0 ORDER BY created_at DESC",
        ).fetchall()
        return [
            Alert(
                id=r["id"],
                type=r["type"],
                target_value=Decimal(str(r["target_value"])),
                asset=r["asset"],
                note=r["note"] or "",
                active=bool(r["active"]),
                triggered=bool(r["triggered"]),
                created_at=r["created_at"],
                triggered_at=r["triggered_at"],
            )
            for r in rows
        ]
    finally:
        conn.close()


def get_all_alerts() -> list[Alert]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY created_at DESC",
        ).fetchall()
        return [
            Alert(
                id=r["id"],
                type=r["type"],
                target_value=Decimal(str(r["target_value"])),
                asset=r["asset"],
                note=r["note"] or "",
                active=bool(r["active"]),
                triggered=bool(r["triggered"]),
                created_at=r["created_at"],
                triggered_at=r["triggered_at"],
            )
            for r in rows
        ]
    finally:
        conn.close()


def delete_alert(alert_id: int) -> bool:
    conn = _get_conn()
    try:
        conn.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        conn.commit()
        return conn.total_changes > 0
    except Exception as e:
        logger.error("Error eliminando alerta: %s", e)
        return False
    finally:
        conn.close()


def check_alerts(current_price: Decimal) -> list[Alert]:
    """
    Verifica todas las alertas activas contra el precio actual.
    Retorna las alertas que se han disparado.
    """
    alerts = get_active_alerts()
    triggered: list[Alert] = []

    for alert in alerts:
        should_trigger = False
        if alert.type == "price_above" and current_price >= alert.target_value:
            should_trigger = True
        elif alert.type == "price_below" and current_price <= alert.target_value:
            should_trigger = True
        elif alert.type == "profit_target":
            avg_price = get_avg_btc_price()
            if avg_price:
                pnl_pct = float((current_price - avg_price) / avg_price * 100)
                if pnl_pct >= float(alert.target_value):
                    should_trigger = True
        elif alert.type == "loss_limit":
            avg_price = get_avg_btc_price()
            if avg_price:
                pnl_pct = float((current_price - avg_price) / avg_price * 100)
                if pnl_pct <= -float(alert.target_value):
                    should_trigger = True

        if should_trigger:
            conn = _get_conn()
            try:
                conn.execute(
                    "UPDATE alerts SET triggered = 1, triggered_at = datetime('now') WHERE id = ?",
                    (alert.id,),
                )
                conn.commit()
            except Exception as e:
                logger.error("Error actualizando alerta: %s", e)
            finally:
                conn.close()
            triggered.append(alert)

    return triggered


# ═════════════════════════════════════════════════════════════
#  Chat ID Registry
# ═════════════════════════════════════════════════════════════

def register_chat_id(chat_id: int, first_name: str = "") -> bool:
    """Registra un chat_id para enviar notificaciones de alertas."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO chat_ids (chat_id, first_name) VALUES (?, ?)",
            (chat_id, first_name),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("Error registrando chat_id: %s", e)
        return False
    finally:
        conn.close()


def get_all_chat_ids() -> list[int]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT chat_id FROM chat_ids").fetchall()
        return [r["chat_id"] for r in rows]
    finally:
        conn.close()


def format_alert_triggered(alert: Alert, current_price: Decimal) -> str:
    """Formatea una alerta disparada."""
    type_labels = {
        "price_above": "Precio por encima de objetivo",
        "price_below": "Precio por debajo de objetivo",
        "profit_target": "Objetivo de ganancia alcanzado",
        "loss_limit": "Límite de pérdida alcanzado",
    }
    label = type_labels.get(alert.type, alert.type)

    lines = [
        f"🚨 **¡Alerta!** 🚨",
        f"**{label}**",
        f"• Activo: {alert.asset}",
        f"• Objetivo: ${float(alert.target_value):,.2f}",
        f"• Precio actual: ${float(current_price):,.2f}",
    ]
    if alert.note:
        lines.append(f"• Nota: {alert.note}")

    return "\n".join(lines)


def format_alert_list(alerts: list[Alert]) -> str:
    """Formatea la lista de alertas."""
    if not alerts:
        return "📋 No hay alertas registradas."

    type_icons = {
        "price_above": "📈",
        "price_below": "📉",
        "profit_target": "💰",
        "loss_limit": "🛑",
    }

    lines = ["🔔 **Alertas Configuradas**\n"]
    for a in alerts:
        icon = type_icons.get(a.type, "🔔")
        status = "✅" if a.triggered else "⏳"
        lines.append(
            f"{status} {icon} `#{a.id}` — {a.asset} "
            f"${float(a.target_value):,.2f} ({a.type})"
        )
        if a.note:
            lines.append(f"   📝 {a.note}")
        if a.triggered_at:
            lines.append(f"   🕐 Activada: {a.triggered_at}")
        lines.append(f"   🕐 Creada: {a.created_at[:16]}")

    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════
#  Importación CSV
# ═════════════════════════════════════════════════════════════

def parse_csv_content(content: str, platform: str) -> list[dict]:
    """
    Parsea contenido CSV de diferentes plataformas.
    Retorna lista de dicts con: type, asset, amount, price, fee, date
    """
    import csv
    import io
    from datetime import datetime

    reader = csv.DictReader(io.StringIO(content))
    trades: list[dict] = []

    if platform == "binance":
        for row in reader:
            # Binance export format varies; try common columns
            side = row.get("Side", row.get("Side of Trade", "")).strip().lower()
            if side not in ("buy", "sell"):
                continue
            pair = row.get("Coin", row.get("Symbol", "")).strip()
            amount_str = row.get("Quantity", row.get("Amount", "0")).strip()
            price_str = row.get("Price", "0").strip()
            fee_str = row.get("Fee", "0").strip()
            date_str = row.get("Date", row.get("Date(UTC)", "")).strip()

            try:
                amount = Decimal(amount_str)
                price = Decimal(price_str)
                fee = Decimal(fee_str)
            except Exception:
                continue

            if amount <= 0 or price <= 0:
                continue

            # Determinar asset
            asset = "BTC"
            if "BTC" in pair or "btc" in pair:
                asset = "BTC"
            elif "USDC" in pair or "usdc" in pair:
                asset = "USDC"
            elif "USDT" in pair or "usdt" in pair:
                asset = "USDT"

            trades.append({
                "type": side,
                "asset": asset,
                "amount": amount,
                "price": price,
                "fee": fee,
                "date": date_str,
            })

    elif platform == "pionex":
        for row in reader:
            side = row.get("Side", row.get("Type", "")).strip().lower()
            if side not in ("buy", "sell"):
                continue
            pair = row.get("Pair", row.get("Symbol", "")).strip()
            amount_str = row.get("Amount", row.get("Filled", "0")).strip()
            price_str = row.get("Price", row.get("Avg Price", "0")).strip()
            fee_str = row.get("Fee", "0").strip()
            date_str = row.get("Time", row.get("Date", "")).strip()

            try:
                amount = Decimal(amount_str)
                price = Decimal(price_str)
                fee = Decimal(fee_str)
            except Exception:
                continue

            if amount <= 0 or price <= 0:
                continue

            asset = "BTC"
            if "BTC" in pair:
                asset = "BTC"
            elif "USDC" in pair:
                asset = "USDC"
            elif "USDT" in pair:
                asset = "USDT"

            trades.append({
                "type": side,
                "asset": asset,
                "amount": amount,
                "price": price,
                "fee": fee,
                "date": date_str,
            })

    else:
        # Generic fallback: try to detect columns
        for row in reader:
            side = row.get("type", row.get("side", row.get("action", ""))).strip().lower()
            if side not in ("buy", "sell"):
                continue
            try:
                amount = Decimal(row.get("amount", row.get("quantity", "0")).strip())
                price = Decimal(row.get("price", row.get("rate", "0")).strip())
                fee = Decimal(row.get("fee", "0").strip())
                asset = row.get("asset", row.get("coin", row.get("symbol", "BTC"))).strip().upper()
            except Exception:
                continue
            if amount <= 0 or price <= 0:
                continue
            trades.append({
                "type": side,
                "asset": asset if asset in ("BTC", "USDC", "USDT") else "BTC",
                "amount": amount,
                "price": price,
                "fee": fee,
                "date": row.get("date", row.get("time", "")).strip(),
            })

    return trades


def import_trades_from_csv(content: str, platform: str, filename: str = "") -> tuple[int, int]:
    """
    Importa trades desde CSV.
    Retorna (importados, errores).
    """
    from datetime import datetime as _dt

    parsed = parse_csv_content(content, platform)
    imported = 0
    errors = 0

    DATE_FORMATS = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    )

    conn = _get_conn()
    try:
        for trade in parsed:
            try:
                # Intentar parsear la fecha del CSV para preservarla
                created_at = None
                date_str = trade.get("date", "")
                if date_str:
                    for fmt in DATE_FORMATS:
                        try:
                            parsed_date = _dt.strptime(date_str[:19], fmt)
                            created_at = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                            break
                        except ValueError:
                            continue

                if created_at:
                    conn.execute(
                        """INSERT INTO trades (type, asset, amount, price, fee, notes, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            trade["type"],
                            trade["asset"],
                            float(trade["amount"]),
                            float(trade["price"]),
                            float(trade["fee"]),
                            f"Importado desde {filename}",
                            created_at,
                        ),
                    )
                else:
                    conn.execute(
                        """INSERT INTO trades (type, asset, amount, price, fee, notes)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            trade["type"],
                            trade["asset"],
                            float(trade["amount"]),
                            float(trade["price"]),
                            float(trade["fee"]),
                            f"Importado desde {filename} ({date_str})",
                        ),
                    )
                imported += 1
            except Exception as e:
                logger.warning("Error importando trade: %s", e)
                errors += 1

        if imported > 0:
            conn.execute(
                "INSERT INTO imported_files (filename, platform, trade_count) VALUES (?, ?, ?)",
                (filename, platform, imported),
            )
        conn.commit()
        logger.info("✅ CSV importado: %s trades, %s errores", imported, errors)
    except Exception as e:
        logger.error("Error en importación CSV: %s", e)
        errors += imported
        imported = 0
    finally:
        conn.close()

    return imported, errors


# ═════════════════════════════════════════════════════════════
#  Gráfica de Evolución del Patrimonio
# ═════════════════════════════════════════════════════════════

def get_portfolio_snapshot_history() -> list[dict]:
    """Obtiene el historial de snapshots para la gráfica de evolución."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM snapshots ORDER BY date ASC",
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def generate_portfolio_evolution_chart() -> Optional[str]:
    """Genera una gráfica de evolución del patrimonio a partir de snapshots."""
    import os
    import time as _time
    from datetime import datetime
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import FuncFormatter

    snapshots = get_portfolio_snapshot_history()
    if len(snapshots) < 2:
        return None

    dates = [datetime.strptime(s["date"], "%Y-%m-%d") for s in snapshots]
    values = [s["total_value"] for s in snapshots]
    btc_prices = [s["btc_price"] for s in snapshots]

    current_value = values[-1]
    initial_value = values[0]
    total_return = ((current_value - initial_value) / initial_value) * 100 if initial_value > 0 else 0

    plt.style.use("dark_background")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={'height_ratios': [3, 1]})
    fig.patch.set_facecolor("#0d1117")

    for ax in (ax1, ax2):
        ax.set_facecolor("#0d1117")

    # Colors
    green = "#10b981"
    gold = "#f7931a"
    blue = "#3b82f6"
    text_color = "#e6edf3"
    grid_color = "#21262d"

    # Top chart: Portfolio value
    is_up = current_value >= initial_value
    line_color = green if is_up else "#ef4444"

    ax1.plot(dates, values, color=line_color, linewidth=2.5, zorder=5)
    ax1.fill_between(dates, min(values), values, color=line_color, alpha=0.1)

    # Current value annotation
    ax1.axhline(y=current_value, color=line_color, linewidth=1, linestyle="--", alpha=0.5)
    ax1.annotate(
        f"${current_value:,.2f}",
        xy=(dates[-1], current_value),
        xytext=(10, 0),
        textcoords="offset points",
        color=line_color,
        fontsize=12,
        fontweight="bold",
        va="center",
    )

    ax1.set_title(
        "💰 Evolución del Patrimonio",
        color=gold,
        fontsize=16,
        fontweight="bold",
        pad=15,
    )
    ax1.grid(axis="y", color=grid_color, linestyle="--", alpha=0.4)
    ax1.grid(axis="x", color=grid_color, linestyle="--", alpha=0.15)
    ax1.tick_params(colors=text_color, labelsize=10)
    ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax1.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=8))
    ax1.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax1.xaxis.get_major_locator()))

    # Info box
    props = dict(boxstyle="round,pad=0.6", facecolor="#161b22", edgecolor=gold, alpha=0.95)
    ax1.text(
        0.02, 0.97,
        f"Valor: ${current_value:,.2f}\nRetorno: {total_return:+.2f}%",
        transform=ax1.transAxes,
        fontsize=10,
        color=text_color,
        verticalalignment="top",
        bbox=props,
        family="monospace",
    )

    # Bottom chart: BTC price overlay
    ax2.plot(dates, btc_prices, color=gold, linewidth=1.5, alpha=0.8, zorder=5)
    ax2.fill_between(dates, min(btc_prices), btc_prices, color=gold, alpha=0.08)
    ax2.set_title("₿ Precio BTC", color=gold, fontsize=12, fontweight="bold", pad=8)
    ax2.grid(axis="y", color=grid_color, linestyle="--", alpha=0.3)
    ax2.tick_params(colors=text_color, labelsize=9)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax2.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=8))
    ax2.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax2.xaxis.get_major_locator()))

    plt.tight_layout()

    chart_dir = "/tmp/tokomagraf"
    os.makedirs(chart_dir, exist_ok=True)
    unique_id = f"evol_{int(_time.time() * 1000)}"
    chart_path = os.path.join(chart_dir, f"portfolio_evolution_{unique_id}.png")
    plt.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    logger.info("📊 Gráfica de evolución generada: %s", chart_path)
    return chart_path


async def generate_portfolio_evolution_chart_async() -> Optional[str]:
    import asyncio
    return await asyncio.to_thread(generate_portfolio_evolution_chart)


# ═════════════════════════════════════════════════════════════
#  Gráfica de Precio con Indicadores Técnicos
# ═════════════════════════════════════════════════════════════

def generate_technical_chart(
    chart_data: list[tuple[datetime, float]],
    days: int = 7,
) -> Optional[str]:
    """Genera una gráfica de BTC con SMA, RSI y MACD."""
    import os
    import time as _time
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import FuncFormatter

    if not chart_data or len(chart_data) < 30:
        return None

    dates = [d for d, _ in chart_data]
    prices = [p for _, p in chart_data]
    current_price = prices[-1]

    # Calcular indicadores
    sma_50_raw = _calculate_sma(prices, min(50, len(prices)))
    sma_200_raw = _calculate_sma(prices, min(200, len(prices)))
    rsi_raw = _calculate_rsi(prices, 14)
    macd_line, macd_signal, macd_hist = _calculate_macd(prices)

    plt.style.use("dark_background")
    fig = plt.figure(figsize=(14, 10))
    fig.patch.set_facecolor("#0d1117")

    # Layout: Price (top), RSI (mid), MACD (bottom)
    gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1.2], hspace=0.35)
    ax_price = fig.add_subplot(gs[0])
    ax_rsi = fig.add_subplot(gs[1])
    ax_macd = fig.add_subplot(gs[2])

    for ax in (ax_price, ax_rsi, ax_macd):
        ax.set_facecolor("#0d1117")

    gold = "#f7931a"
    green = "#10b981"
    red = "#ef4444"
    blue = "#3b82f6"
    purple = "#8b5cf6"
    orange = "#f59e0b"
    text_color = "#e6edf3"
    grid_color = "#21262d"

    # ── Price chart with SMAs ──
    is_up = prices[-1] >= prices[0]
    line_color = green if is_up else red

    ax_price.plot(dates, prices, color=line_color, linewidth=2, zorder=5, label="Precio")

    # SMA 50
    sma_50_vals = [v if v is not None else float('nan') for v in sma_50_raw]
    ax_price.plot(dates, sma_50_vals, color=orange, linewidth=1.5, alpha=0.8, linestyle="--", label="SMA 50")

    # SMA 200
    sma_200_vals = [v if v is not None else float('nan') for v in sma_200_raw]
    ax_price.plot(dates, sma_200_vals, color=purple, linewidth=1.5, alpha=0.8, linestyle="--", label="SMA 200")

    ax_price.fill_between(dates, min(prices), prices, color=line_color, alpha=0.08)

    # Current price line
    ax_price.axhline(y=current_price, color=text_color, linewidth=0.8, linestyle=":", alpha=0.4)
    ax_price.annotate(
        f"${current_price:,.0f}",
        xy=(dates[-1], current_price),
        xytext=(10, 0),
        textcoords="offset points",
        color=text_color,
        fontsize=11,
        fontweight="bold",
        va="center",
    )

    ax_price.set_title(
        f"📊 BTC/USD — Últimos {days} días (con SMA, RSI, MACD)",
        color=gold,
        fontsize=15,
        fontweight="bold",
        pad=12,
    )
    ax_price.grid(axis="y", color=grid_color, linestyle="--", alpha=0.3)
    ax_price.tick_params(colors=text_color, labelsize=9)
    ax_price.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax_price.legend(loc="upper left", fontsize=9, facecolor="#161b22", edgecolor=grid_color, labelcolor=text_color)

    # ── RSI ──
    rsi_vals = [v if v is not None else float('nan') for v in rsi_raw]
    rsi_color = green if rsi_raw[-1] is not None and rsi_raw[-1] < 50 else red if rsi_raw[-1] is not None else text_color
    ax_rsi.plot(dates, rsi_vals, color=rsi_color, linewidth=1.8, zorder=5)
    ax_rsi.axhline(y=70, color=red, linewidth=1, linestyle="--", alpha=0.5)
    ax_rsi.axhline(y=30, color=green, linewidth=1, linestyle="--", alpha=0.5)
    ax_rsi.axhline(y=50, color=text_color, linewidth=0.5, linestyle=":", alpha=0.3)
    ax_rsi.fill_between(dates, 30, 70, color=text_color, alpha=0.05)

    # RSI labels
    if rsi_raw[-1] is not None:
        ax_rsi.annotate(
            f"RSI: {rsi_raw[-1]:.1f}" if rsi_raw[-1] is not None else "RSI: --",
            xy=(dates[-1], rsi_raw[-1] or 50),
            xytext=(10, 0),
            textcoords="offset points",
            color=text_color,
            fontsize=10,
            fontweight="bold",
            va="center",
        )

    ax_rsi.set_ylim(0, 100)
    ax_rsi.set_title("RSI (14)", color=text_color, fontsize=12, fontweight="bold", pad=8)
    ax_rsi.grid(axis="y", color=grid_color, linestyle="--", alpha=0.3)
    ax_rsi.tick_params(colors=text_color, labelsize=8)
    ax_rsi.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
    ax_rsi.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax_rsi.xaxis.get_major_locator()))

    # ── MACD ──
    macd_vals = [v if v is not None else float('nan') for v in macd_line]
    signal_vals = [v if v is not None else float('nan') for v in macd_signal]
    hist_vals = [v if v is not None else 0 for v in macd_hist]

    ax_macd.plot(dates, macd_vals, color=blue, linewidth=1.5, label="MACD")
    ax_macd.plot(dates, signal_vals, color=orange, linewidth=1.5, label="Signal")

    # Histogram bars
    for i in range(len(dates)):
        if i < len(hist_vals):
            color = green if hist_vals[i] >= 0 else red
            ax_macd.bar(dates[i], hist_vals[i], width=0.8, color=color, alpha=0.6)

    ax_macd.axhline(y=0, color=text_color, linewidth=0.5, linestyle="--", alpha=0.3)
    ax_macd.set_title("MACD", color=text_color, fontsize=12, fontweight="bold", pad=8)
    ax_macd.grid(axis="y", color=grid_color, linestyle="--", alpha=0.3)
    ax_macd.tick_params(colors=text_color, labelsize=8)
    ax_macd.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=6))
    ax_macd.xaxis.set_major_formatter(mdates.ConciseDateFormatter(ax_macd.xaxis.get_major_locator()))
    ax_macd.legend(loc="upper left", fontsize=8, facecolor="#161b22", edgecolor=grid_color, labelcolor=text_color)

    plt.tight_layout()

    chart_dir = "/tmp/tokomagraf"
    os.makedirs(chart_dir, exist_ok=True)
    unique_id = f"tech_{days}d_{int(_time.time() * 1000)}"
    chart_path = os.path.join(chart_dir, f"btc_technical_{unique_id}.png")
    plt.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    logger.info("📊 Gráfica técnica BTC generada: %s", chart_path)
    return chart_path


async def generate_technical_chart_async(days: int = 7) -> Optional[str]:
    import asyncio
    chart_data = await fetch_btc_chart_data(days)
    if not chart_data:
        return None
    return await asyncio.to_thread(generate_technical_chart, chart_data, days)


def format_usd(value: Decimal) -> str:
    neg = value < 0
    if neg:
        value = -value
    formatted = f"${value:,.2f}"
    return f"-{formatted}" if neg else formatted


def format_btc(value: Decimal) -> str:
    """Formatea BTC con hasta 8 decimales, eliminando ceros innecesarios."""
    formatted = f"{value:.8f}".rstrip("0").rstrip(".")
    return formatted


def format_pct(value: float) -> str:
    """Formatea porcentaje con signo: +12.34% o -5.67%"""
    return f"{value:+.2f}%"
