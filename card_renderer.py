# =============================================================
# card_renderer.py — Generador de tarjeta de precio BTC
# Renderiza HTML con Jinja2 y captura screenshot con Playwright
# =============================================================

import logging
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import jinja2

import portfolio

logger = logging.getLogger("tokomagraf_card")

TEMPLATES_DIR = Path(__file__).parent / "card_templates"

# ── Jinja2 Environment ──────────────────────────────────────
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
    undefined=jinja2.StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    auto_reload=True,
)


# ── Filtros Jinja2 ──────────────────────────────────────────


def _format_usd(value: Any) -> str:
    try:
        d = Decimal(str(value))
        neg = d < 0
        if neg:
            d = -d
        formatted = f"${d:,.2f}"
        return f"-{formatted}" if neg else formatted
    except Exception:
        return str(value)


_jinja_env.filters["usd"] = _format_usd


# ── Helpers ─────────────────────────────────────────────────


def _render_html(template_name: str, **context: Any) -> str:
    template = _jinja_env.get_template(template_name)
    return template.render(**context)


# ── Caché de imágenes ──────────────────────────────────────

CACHE_TTL = 60
_cache: dict[str, tuple[float, bytes]] = {}


def _cache_key(*args, **kwargs) -> str:
    parts = [str(a) for a in args]
    for k, v in sorted(kwargs.items()):
        parts.append(f"{k}={v}")
    return "|".join(parts)


def _cache_get(key: str) -> Optional[bytes]:
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[0]) < CACHE_TTL:
        logger.debug("Cache hit: %s", key[:80])
        return entry[1]
    return None


def _cache_set(key: str, data: bytes) -> None:
    _cache[key] = (time.monotonic(), data)
    if len(_cache) > 20:
        now = time.monotonic()
        expired = [k for k, (t, _) in _cache.items() if (now - t) >= CACHE_TTL]
        for k in expired:
            del _cache[k]


def invalidate_cache():
    _cache.clear()
    logger.debug("Cache limpiado")


# ── Datos de la tarjeta ─────────────────────────────────────


@dataclass
class CardData:
    price: str
    change_pct: str
    change_class: str
    change_arrow: str
    high_24h: str
    low_24h: str
    spark_width: str
    timestamp: str


def build_card_data(
    price_usd: Decimal,
    change_24h_pct: Optional[float],
    high_24h: Optional[Decimal],
    low_24h: Optional[Decimal],
) -> CardData:
    price_str = f"{price_usd:,.2f}"

    if change_24h_pct is not None:
        change_pct_str = f"{change_24h_pct:+.2f}"
        if change_24h_pct > 0:
            change_class = "positive"
            change_arrow = "▲"
        elif change_24h_pct < 0:
            change_class = "negative"
            change_arrow = "▼"
        else:
            change_class = "neutral"
            change_arrow = "—"
    else:
        change_pct_str = "0.00"
        change_class = "neutral"
        change_arrow = "—"

    high_str = f"{high_24h:,.2f}" if high_24h else price_str
    low_str = f"{low_24h:,.2f}" if low_24h else price_str

    if high_24h and low_24h and high_24h > low_24h:
        ratio = float((price_usd - low_24h) / (high_24h - low_24h))
        spark_width = max(1, min(100, round(ratio * 100)))
    else:
        spark_width = 50

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return CardData(
        price=price_str,
        change_pct=change_pct_str,
        change_class=change_class,
        change_arrow=change_arrow,
        high_24h=high_str,
        low_24h=low_str,
        spark_width=str(spark_width),
        timestamp=ts,
    )


# ── Renderizado con Playwright ──────────────────────────────


async def _render_html_to_bytes(html: str, card_selector: str) -> Optional[bytes]:
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", encoding="utf-8", delete=False,
    )
    try:
        tmp.write(html)
        tmp.close()
        tmp_path = tmp.name

        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 500, "height": 700},
                device_scale_factor=2,
            )
            page = await context.new_page()

            await page.goto(f"file://{tmp_path}", wait_until="networkidle")
            await page.wait_for_timeout(300)

            card_element = page.locator(card_selector)
            await card_element.wait_for(state="visible", timeout=5000)

            screenshot_bytes = await card_element.screenshot(type="png", scale="device")
            await browser.close()

        return screenshot_bytes

    except Exception as e:
        logger.error("Error renderizando con Playwright: %s", e)
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ── Datos del dashboard ──────────────────────────────────────


@dataclass
class DashboardCardData:
    total_value_str: str
    total_pnl_pct_str: str
    pnl_absolute_str: str
    pnl_arrow: str
    pnl_class: str
    rec_class: str
    recommendation: str
    recommendation_explanation: str
    btc_balance_str: str
    usdc_balance_str: str
    total_invested_str: str
    avg_price_str: str
    current_price_str: str
    btc_change_str: str
    btc_change_class: str
    target_price_str: str
    target_pct_str: str
    progress_str: str
    progress_width: str
    progress_class: str
    has_profits: bool
    daily_profit_str: str
    monthly_profit_str: str
    annualized_str: str
    daily_class: str
    monthly_class: str
    annual_class: str
    trade_count: str
    first_trade_date: str
    timestamp: str


def build_dashboard_card_data(data: portfolio.PortfolioData) -> DashboardCardData:
    """Convierte PortfolioData en datos formateados para el template."""
    import portfolio as pf

    # Valor total
    total_value_str = pf.format_usd(data.portfolio_value)

    # P&L
    pnl_arrow = "▲" if data.total_pnl >= 0 else "▼"
    pnl_class = "positive" if data.total_pnl >= 0 else "negative"
    if data.total_pnl == 0:
        pnl_class = "neutral"

    total_pnl_pct_str = pf.format_pct(data.total_pnl_pct)
    pnl_absolute_str = pf.format_usd(data.total_pnl)

    # Recomendación clases
    if "Compra" in data.recommendation:
        rec_class = "buy"
    elif "Venta" in data.recommendation:
        rec_class = "sell"
    else:
        rec_class = "hold"

    # Balances
    btc_balance_str = pf.format_btc(data.btc_balance)
    usdc_balance_str = pf.format_usd(data.usdc_balance)
    total_invested_str = pf.format_usd(data.total_invested)

    # Precios
    avg_price_str = pf.format_usd(data.avg_btc_price) if data.avg_btc_price else "—"
    current_price_str = pf.format_usd(data.btc_price)
    target_price_str = pf.format_usd(data.target_price) if data.target_price else "—"
    target_pct_str = f"{data.target_pct:.0f}%"

    # BTC price change
    if data.btc_price_change_24h is not None:
        btc_change_str = pf.format_pct(data.btc_price_change_24h)
        btc_change_class = "up" if data.btc_price_change_24h >= 0 else "down"
    else:
        btc_change_str = ""
        btc_change_class = ""

    # Progreso a objetivo
    if data.progress_to_target is not None:
        p = data.progress_to_target
        progress_str = f"{p:.1f}%"
        progress_width = str(min(100, max(0, round(p))))
        if p >= 100:
            progress_class = "target"
        elif p >= 66:
            progress_class = "high"
        elif p >= 33:
            progress_class = "medium"
        else:
            progress_class = "low"
    else:
        progress_str = "—"
        progress_width = "0"
        progress_class = "low"

    # Profits
    has_profits = data.daily_profit is not None or data.monthly_profit is not None

    def _profit_str(val, klass):
        if val is None:
            return "—"
        return pf.format_usd(val)

    daily_str = _profit_str(data.daily_profit, "")
    monthly_str = _profit_str(data.monthly_profit, "")

    daily_class = "positive" if (data.daily_profit and data.daily_profit >= 0) else "negative" if (data.daily_profit and data.daily_profit < 0) else "muted"
    monthly_class = "positive" if (data.monthly_profit and data.monthly_profit >= 0) else "negative" if (data.monthly_profit and data.monthly_profit < 0) else "muted"

    # Anualizado
    if data.annualized_return is not None:
        annualized_str = pf.format_pct(data.annualized_return)
        annual_class = "positive" if data.annualized_return >= 0 else "negative"
    else:
        annualized_str = "—"
        annual_class = "muted"

    # Metadata
    trade_count = str(data.trade_count)
    first_trade_date = data.first_trade_date[:10] if data.first_trade_date else "—"

    return DashboardCardData(
        total_value_str=total_value_str,
        total_pnl_pct_str=total_pnl_pct_str,
        pnl_absolute_str=pnl_absolute_str,
        pnl_arrow=pnl_arrow,
        pnl_class=pnl_class,
        rec_class=rec_class,
        recommendation=data.recommendation,
        recommendation_explanation=data.recommendation_explanation,
        btc_balance_str=btc_balance_str,
        usdc_balance_str=usdc_balance_str,
        total_invested_str=total_invested_str,
        avg_price_str=avg_price_str,
        current_price_str=current_price_str,
        btc_change_str=btc_change_str,
        btc_change_class=btc_change_class,
        target_price_str=target_price_str,
        target_pct_str=target_pct_str,
        progress_str=progress_str,
        progress_width=progress_width,
        progress_class=progress_class,
        has_profits=has_profits,
        daily_profit_str=daily_str,
        monthly_profit_str=monthly_str,
        annualized_str=annualized_str,
        daily_class=daily_class,
        monthly_class=monthly_class,
        annual_class=annual_class,
        trade_count=trade_count,
        first_trade_date=first_trade_date,
        timestamp=data.updated_at,
    )


async def generate_dashboard_card(
    data: portfolio.PortfolioData,
    *,
    force: bool = False,
) -> Optional[bytes]:
    """Genera una tarjeta PNG con el dashboard de la cartera."""
    ck = _cache_key("dashboard", data.portfolio_value, data.updated_at)
    if not force:
        cached = _cache_get(ck)
        if cached is not None:
            return cached

    card_data = build_dashboard_card_data(data)

    html = _render_html(
        "dashboard_card.html",
        **card_data.__dict__,
    )
    img = await _render_html_to_bytes(html, "#dashboardCard")
    if img is not None:
        _cache_set(ck, img)
    return img


# ── Generar tarjeta de precio BTC ───────────────────────────


async def generate_price_card(
    price_usd: Decimal,
    change_24h_pct: Optional[float] = None,
    high_24h: Optional[Decimal] = None,
    low_24h: Optional[Decimal] = None,
    *,
    force: bool = False,
) -> Optional[bytes]:
    """Genera una tarjeta PNG con el precio de BTC."""
    ck = _cache_key("price", price_usd, change_24h_pct, high_24h, low_24h)
    if not force:
        cached = _cache_get(ck)
        if cached is not None:
            return cached

    data = build_card_data(price_usd, change_24h_pct, high_24h, low_24h)

    html = _render_html(
        "precio_card.html",
        # Valores raw para filtros Jinja2
        price_raw=price_usd,
        high_24h_raw=high_24h,
        low_24h_raw=low_24h,
        change_pct_raw=change_24h_pct,
        # Valores pre-formateados
        change_pct=data.change_pct,
        change_class=data.change_class,
        change_arrow=data.change_arrow,
        spark_width=data.spark_width,
        timestamp=data.timestamp,
    )
    img = await _render_html_to_bytes(html, "#priceCard")
    if img is not None:
        _cache_set(ck, img)
    return img
