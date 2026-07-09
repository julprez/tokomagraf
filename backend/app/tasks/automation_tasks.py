# =============================================================
# tasks/automation_tasks.py — Tareas de automatización periódica
# =============================================================
#
# Cada minuto:  Actualizar precio BTC, portfolio, P&L, gráficos, snapshot
# Cada 24h:     Generar resumen, rentabilidad, balance, max drawdown
#

import logging
import os
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app

logger = logging.getLogger("tokomagraf_automation")

# Conexión síncrona para Celery (usa la misma URL pero sin async)
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://tokomagraf:changeme@db:5432/tokomagraf")
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
elif DATABASE_URL.startswith("sqlite+aiosqlite://"):
    DATABASE_URL = DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


# ── Cada 1 minuto ─────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def update_market_data(self):
    """
    Actualiza datos de mercado y portfolio cada minuto.
    - Precio BTC actual
    - Portfolio (valor, P&L)
    - Snapshot diario (una vez por día)
    """
    try:
        import requests as sync_requests
    except ImportError:
        logger.error("requests no instalado, no se puede actualizar")
        return

    # 1. Obtener precio BTC
    try:
        resp = sync_requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true",
            timeout=10,
        )
        if resp.status_code == 200:
            btc_data = resp.json().get("bitcoin", {})
            btc_price = btc_data.get("usd")
            logger.info("Precio BTC actualizado: $%.2f", btc_price)
        else:
            logger.warning("CoinGecko respondió %s", resp.status_code)
            return
    except Exception as e:
        logger.error("Error actualizando precio BTC: %s", e)
        return

    # 2. Actualizar snapshots de todos los usuarios
    with Session(engine) as session:
        users = session.execute(text("SELECT id FROM users")).fetchall()
        today = date.today()

        for (user_id,) in users:
            try:
                # Calcular portfolio del usuario
                ops = session.execute(
                    text("""
                        SELECT tipo, activo, cantidad, precio, comision
                        FROM operations
                        WHERE user_id = :uid
                    """),
                    {"uid": user_id},
                ).fetchall()

                btc = usdc = eur = total_invested = 0.0
                for op in ops:
                    tipo, activo, cantidad, precio, comision = op
                    if tipo == "buy":
                        if activo == "BTC":
                            btc += cantidad
                            total_invested += cantidad * precio + comision
                        elif activo == "USDC":
                            usdc += cantidad
                            total_invested += cantidad * precio + comision
                        elif activo == "EUR":
                            eur += cantidad
                            total_invested += cantidad * precio + comision
                    elif tipo == "sell":
                        if activo == "BTC":
                            btc -= cantidad
                            usdc += cantidad * precio - comision
                        elif activo == "USDC":
                            usdc -= cantidad
                        elif activo == "EUR":
                            eur -= cantidad
                    elif tipo == "deposit":
                        if activo == "USDC":
                            usdc += cantidad
                            total_invested += cantidad
                        elif activo == "EUR":
                            eur += cantidad
                            total_invested += cantidad
                    elif tipo == "withdraw":
                        if activo == "USDC":
                            usdc -= cantidad
                        elif activo == "EUR":
                            eur -= cantidad

                portfolio_value = round(btc * btc_price + usdc + eur, 2)
                pnl = round(portfolio_value - total_invested, 2) if total_invested > 0 else 0.0

                # Guardar snapshot diario (solo si no existe para hoy)
                existing = session.execute(
                    text("SELECT id FROM daily_history WHERE user_id = :uid AND fecha = :today"),
                    {"uid": user_id, "today": today},
                ).fetchone()

                if not existing:
                    # Ganancia del día vs ayer
                    yesterday_data = session.execute(
                        text("SELECT valor_portfolio FROM daily_history WHERE user_id = :uid AND fecha = :y ORDER BY fecha DESC LIMIT 1"),
                        {"uid": user_id, "y": today - timedelta(days=1)},
                    ).fetchone()
                    ganancia = round(portfolio_value - yesterday_data[0], 2) if yesterday_data else 0.0

                    session.execute(
                        text("""
                            INSERT INTO daily_history (user_id, fecha, valor_portfolio, ganancia_dia, btc, usdc)
                            VALUES (:uid, :today, :val, :gan, :btc, :usdc)
                        """),
                        {"uid": user_id, "today": today, "val": portfolio_value,
                         "gan": ganancia, "btc": btc, "usdc": usdc},
                    )

            except Exception as e:
                logger.error("Error actualizando user %s: %s", user_id, e)
                continue

        session.commit()

    logger.info("✅ Datos de mercado actualizados — %s usuarios procesados", len(users))


# ── Cada 24h ──────────────────────────────────────────────

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_daily_summary(self):
    """
    Genera resumen diario con rentabilidad, balance y máximo drawdown.
    """
    import json
    from datetime import date, timedelta

    today = date.today()
    yesterday = today - timedelta(days=1)

    with Session(engine) as session:
        users = session.execute(text("SELECT id, name FROM users")).fetchall()

        for user_id, user_name in users:
            try:
                # Obtener historial completo
                history = session.execute(
                    text("""
                        SELECT fecha, valor_portfolio, ganancia_dia
                        FROM daily_history
                        WHERE user_id = :uid
                        ORDER BY fecha ASC
                    """),
                    {"uid": user_id},
                ).fetchall()

                if not history:
                    continue

                current_value = history[-1].valor_portfolio
                initial_value = history[0].valor_portfolio

                # Rentabilidad total
                if initial_value > 0:
                    total_return = round((current_value - initial_value) / initial_value * 100, 2)
                else:
                    total_return = 0.0

                # Rentabilidad últimos 7, 30, 90 días
                returns = {}
                for days, label in [(7, "7d"), (30, "30d"), (90, "90d")]:
                    cutoff = today - timedelta(days=days)
                    past = [h for h in history if h.fecha <= cutoff]
                    if past:
                        past_val = past[-1].valor_portfolio
                        returns[label] = round((current_value - past_val) / past_val * 100, 2) if past_val > 0 else 0.0

                # Máximo drawdown (peak-to-trough)
                peak = history[0].valor_portfolio
                max_drawdown = 0.0
                drawdown_start = None
                drawdown_end = None
                current_dd_start = None

                for h in history:
                    if h.valor_portfolio > peak:
                        peak = h.valor_portfolio
                        current_dd_start = None
                    else:
                        dd = (peak - h.valor_portfolio) / peak * 100
                        if current_dd_start is None:
                            current_dd_start = h.fecha
                        if dd > max_drawdown:
                            max_drawdown = dd
                            drawdown_start = current_dd_start
                            drawdown_end = h.fecha

                # Beneficio promedio por día
                days_active = (history[-1].fecha - history[0].fecha).days
                avg_daily_return = round(total_return / days_active, 2) if days_active > 0 else 0.0

                # Ratio win/loss (días positivos vs negativos)
                win_days = sum(1 for h in history if h.ganancia_dia > 0)
                loss_days = sum(1 for h in history if h.ganancia_dia < 0)
                total_days = win_days + loss_days

                # Crear resumen como registro en una tabla de summaries o log
                summary_data = {
                    "user_id": user_id,
                    "fecha": today.isoformat(),
                    "total_return_pct": total_return,
                    "period_returns": returns,
                    "max_drawdown_pct": round(max_drawdown, 2),
                    "drawdown_start": drawdown_start.isoformat() if drawdown_start else None,
                    "drawdown_end": drawdown_end.isoformat() if drawdown_end else None,
                    "avg_daily_return_pct": avg_daily_return,
                    "win_days": win_days,
                    "loss_days": loss_days,
                    "total_days_with_trades": total_days,
                    "win_rate": round(win_days / total_days * 100, 1) if total_days > 0 else 0,
                    "portfolio_value": current_value,
                }

                # Guardar en tabla de summaries (crear si no existe)
                session.execute(
                    text("""
                        INSERT INTO daily_summaries (user_id, fecha, total_return_pct, max_drawdown_pct,
                            avg_daily_return_pct, win_rate, portfolio_value, raw_data)
                        VALUES (:uid, :fecha, :total_return, :max_dd, :avg_daily, :win_rate, :pv, :raw)
                        ON CONFLICT (user_id, fecha) DO NOTHING
                    """),
                    {
                        "uid": user_id,
                        "fecha": today,
                        "total_return": summary_data["total_return_pct"],
                        "max_dd": summary_data["max_drawdown_pct"],
                        "avg_daily": summary_data["avg_daily_return_pct"],
                        "win_rate": summary_data["win_rate"],
                        "pv": current_value,
                        "raw": json.dumps(summary_data),
                    },
                )

                logger.info(
                    "Resumen %s — retorno: %.1f%%, drawdown máx: %.1f%%, win rate: %.1f%%",
                    user_name, total_return, max_drawdown,
                    win_days / total_days * 100 if total_days > 0 else 0,
                )

            except Exception as e:
                logger.error("Error generando resumen para user %s: %s", user_id, e)
                continue

        session.commit()

    logger.info("✅ Resúmenes diarios generados para todos los usuarios")
