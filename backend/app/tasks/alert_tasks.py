# =============================================================
# alert_tasks.py — Tareas Celery para verificar alertas
# =============================================================

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.models.models import Alert, Notification

logger = logging.getLogger("tokomagraf_tasks")

# Conexión síncrona a BD para Celery (no puede usar async)
DB_URL = os.environ.get("DATABASE_URL", "sqlite:////app/data/tokomagraf.db")
if DB_URL.startswith("postgresql+asyncpg://"):
    DB_URL = DB_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
elif DB_URL.startswith("sqlite+aiosqlite://"):
    DB_URL = DB_URL.replace("sqlite+aiosqlite://", "sqlite://", 1)

sync_engine = create_engine(DB_URL, pool_pre_ping=True)


def _get_btc_price() -> Optional[float]:
    """Obtiene precio BTC desde CoinGecko (síncrono para Celery)."""
    try:
        resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("bitcoin", {}).get("usd")
    except Exception as e:
        logger.error("Error fetching BTC price: %s", e)
    return None


def _calculate_pnl_pct(user_id: int, session: Session) -> Optional[float]:
    """Calcula el P&L % del usuario basado en sus operaciones de BTC."""
    from app.models.models import Operation

    buys = session.execute(
        select(Operation).where(
            Operation.user_id == user_id,
            Operation.tipo == "buy",
            Operation.activo == "BTC",
        )
    ).scalars().all()

    sells = session.execute(
        select(Operation).where(
            Operation.user_id == user_id,
            Operation.tipo == "sell",
            Operation.activo == "BTC",
        )
    ).scalars().all()

    total_btc = sum(op.cantidad for op in buys) - sum(op.cantidad for op in sells)
    if total_btc <= 0:
        return None

    total_cost = sum(op.cantidad * op.precio + op.comision for op in buys)
    avg_price = total_cost / sum(op.cantidad for op in buys) if sum(op.cantidad for op in buys) > 0 else 0

    price = _get_btc_price()
    if not price or avg_price == 0:
        return None

    pnl_pct = ((price - avg_price) / avg_price) * 100
    return round(pnl_pct, 2)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def check_all_alerts(self):
    """Verifica todas las alertas activas y crea notificaciones."""
    logger.info("🔍 Verificando alertas activas…")

    price = _get_btc_price()
    if price is None:
        logger.warning("No se pudo obtener precio BTC, reintentando…")
        self.retry()
        return

    alerts: list[Alert] = []
    triggered_count = 0

    session: Session = Session(sync_engine)
    try:
        alerts = session.execute(
            select(Alert).where(Alert.active == True, Alert.triggered == False)  # noqa: E712
        ).scalars().all()

        for alert in alerts:
            should_trigger = False

            if alert.alert_type == "price_above" and price >= alert.target_value:
                should_trigger = True
            elif alert.alert_type == "price_below" and price <= alert.target_value:
                should_trigger = True
            elif alert.alert_type in ("profit_target", "loss_limit"):
                # Calcular P&L del usuario para alertas basadas en rentabilidad
                pnl_pct = _calculate_pnl_pct(alert.user_id, session)
                if pnl_pct is not None:
                    if alert.alert_type == "profit_target" and pnl_pct >= alert.target_value:
                        should_trigger = True
                    elif alert.alert_type == "loss_limit" and pnl_pct <= -alert.target_value:
                        should_trigger = True

            if should_trigger:
                alert.triggered = True
                alert.triggered_at = datetime.now(timezone.utc)

                notif = Notification(
                    user_id=alert.user_id,
                    alert_id=alert.id,
                    title=_alert_title(alert.alert_type),
                    message=_alert_message(alert, price),
                    notif_type=alert.alert_type,
                    target_value=alert.target_value,
                    current_price=price,
                )
                session.add(notif)
                triggered_count += 1
                logger.info("🚨 Alerta #%d disparada para usuario %d", alert.id, alert.user_id)

        session.commit()
        logger.info("✅ Verificación: %d alertas, %d disparadas", len(alerts), triggered_count)

    except Exception as e:
        session.rollback()
        logger.error("Error verificando alertas: %s", e)
        raise
    finally:
        session.close()

    return {"checked": len(alerts), "triggered": triggered_count, "price": price}


def _alert_title(alert_type: str) -> str:
    titles = {
        "price_above": "🚨 Precio superó objetivo",
        "price_below": "🚨 Precio cayó del objetivo",
        "profit_target": "💰 Ganancia objetivo alcanzada",
        "loss_limit": "🛑 Límite de pérdida alcanzado",
    }
    return titles.get(alert_type, "🔔 Alerta disparada")


def _alert_message(alert: Alert, current_price: float) -> str:
    base = (
        f"Activo: {alert.asset}\n"
        f"Objetivo: ${alert.target_value:,.2f}\n"
        f"Precio actual: ${current_price:,.2f}"
    )
    if alert.note:
        base += f"\nNota: {alert.note}"
    return base
