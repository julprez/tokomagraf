# =============================================================
# tasks/intelligence_tasks.py — Notificaciones Inteligentes
# =============================================================
#
# Ejecuta el motor de inteligencia periódicamente y crea
# notificaciones cuando detecta patrones interesantes:
# - Compras en caídas significativas
# - Ventas prematuras con alta oportunidad perdida
# - Mejora/empeoramiento del precio medio vs DCA
#

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app

logger = logging.getLogger("tokomagraf_intelligence")

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://tokomagraf:changeme@db:5432/tokomagraf")
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
elif DATABASE_URL.startswith("sqlite+aiosqlite://"):
    DATABASE_URL = DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Umbrales para generar notificaciones
UMBRAL_COMPRA_CAIDA = 10.0  # % mínimo de caída para notificar
UMBRAL_VENTA_PERDIDA = 500.0  # $ mínimo de pérdida estimada para notificar


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def generate_intelligence_notifications(self):
    """
    Ejecuta el motor de inteligencia para cada usuario y crea
    notificaciones con los hallazgos más relevantes.

    Se ejecuta cada 6 horas para evitar spam de notificaciones.
    """
    logger.info("🧠 Generando notificaciones inteligentes…")

    with Session(engine) as session:
        users = session.execute(text("SELECT id, name FROM users")).fetchall()

        for user_id, user_name in users:
            try:
                _process_user_notifications(session, user_id, user_name)
            except Exception as e:
                logger.error("Error procesando user %s: %s", user_id, e)
                continue

        session.commit()

    logger.info("✅ Notificaciones inteligentes generadas para %s usuarios", len(users))
    return {"users_processed": len(users)}


def _process_user_notifications(session: Session, user_id: int, user_name: str):
    """Procesa un usuario y crea notificaciones si hay hallazgos nuevos."""
    import requests as sync_requests

    # 1. Obtener operaciones del usuario
    ops = session.execute(
        text("""
            SELECT id, tipo, activo, cantidad, precio, comision, fecha
            FROM operations
            WHERE user_id = :uid
            ORDER BY fecha ASC
        """),
        {"uid": user_id},
    ).fetchall()

    if len(ops) < 2:
        return

    # 2. Obtener precio BTC actual y chart
    try:
        resp = sync_requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=10,
        )
        btc_now = resp.json().get("bitcoin", {}).get("usd", 0) if resp.status_code == 200 else 0
    except Exception:
        btc_now = 0

    if btc_now == 0:
        return

    # 3. Obtener chart BTC para precios históricos
    days_span = 365
    try:
        chart_resp = sync_requests.get(
            f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days={days_span}",
            timeout=10,
        )
        chart_data = chart_resp.json().get("prices", []) if chart_resp.status_code == 200 else []
    except Exception:
        chart_data = []

    if not chart_data:
        return

    # Indexar precios por fecha
    price_map = {}
    for ts_ms, price in chart_data:
        dt = datetime.fromtimestamp(ts_ms / 1000)
        fecha_key = dt.date().isoformat()
        if fecha_key not in price_map:
            price_map[fecha_key] = price

    # 4. Analizar compras en caídas (últimas 24h de operaciones)
    hoy = datetime.now().date()
    ayer = hoy - timedelta(days=1)

    buys = [op for op in ops if op.tipo == "buy" and op.activo == "BTC"]
    sells = [op for op in ops if op.tipo == "sell" and op.activo == "BTC"]

    # Analizar última compra
    if buys:
        ultima_compra = buys[-1]
        fecha_key = ultima_compra.fecha.isoformat()[:10] if hasattr(ultima_compra.fecha, 'isoformat') else str(ultima_compra.fecha)[:10]
        precio_compra = ultima_compra.precio

        # Precio 7 días antes
        from datetime import date, timedelta
        try:
            fecha_dt = date.fromisoformat(fecha_key)
            fecha_7d = (fecha_dt - timedelta(days=7)).isoformat()
            precio_7d = price_map.get(fecha_7d) or price_map.get(fecha_key)
        except Exception:
            precio_7d = None

        if precio_7d and precio_compra < precio_7d:
            caida = (precio_7d - precio_compra) / precio_7d * 100
            if caida >= UMBRAL_COMPRA_CAIDA:
                _crear_notification(
                    session, user_id,
                    notif_type="buy_dip",
                    title="📉 Compraste en caída significativa",
                    message=(
                        f"Compraste {ultima_compra.cantidad:.6f} BTC a "
                        f"${precio_compra:,.0f}, un {caida:.0f}% menos que "
                        f"7 días antes (${precio_7d:,.0f}). "
                        f"Buen timing de mercado."
                    ),
                )

    # Analizar última venta
    if sells:
        ultima_venta = sells[-1]
        fecha_key = ultima_venta.fecha.isoformat()[:10] if hasattr(ultima_venta.fecha, 'isoformat') else str(ultima_venta.fecha)[:10]
        precio_venta = ultima_venta.precio

        # Precio 30 días después
        try:
            fecha_dt = date.fromisoformat(fecha_key)
            fecha_30d = (fecha_dt + timedelta(days=30)).isoformat()
            precio_30d = price_map.get(fecha_30d)
        except Exception:
            precio_30d = None

        if precio_30d and precio_30d > precio_venta:
            subida = (precio_30d - precio_venta) / precio_venta * 100
            perdida = ultima_venta.cantidad * (precio_30d - precio_venta)
            if perdida >= UMBRAL_VENTA_PERDIDA:
                _crear_notification(
                    session, user_id,
                    notif_type="sell_premature",
                    title="😤 Venta prematura detectada",
                    message=(
                        f"Vendiste {ultima_venta.cantidad:.6f} BTC a "
                        f"${precio_venta:,.0f} y 30 días después "
                        f"cotizaba a ${precio_30d:,.0f} (+{subida:.0f}%). "
                        f"Esto representó una oportunidad perdida de "
                        f"${perdida:,.0f}."
                    ),
                    target_value=precio_venta,
                    current_price=precio_30d,
                )
        elif precio_30d and precio_30d < precio_venta:
            caida_post = (precio_venta - precio_30d) / precio_venta * 100
            if caida_post > 5:
                _crear_notification(
                    session, user_id,
                    notif_type="sell_good",
                    title="✅ Venta acertada",
                    message=(
                        f"Vendiste {ultima_venta.cantidad:.6f} BTC a "
                        f"${precio_venta:,.0f} y 30 días después "
                        f"el precio cayó a ${precio_30d:,.0f} (-{caida_post:.0f}%). "
                        f"Buena decisión de tomar ganancias."
                    ),
                )

    # Comparativa precio medio vs DCA (si tiene DCA configurado)
    dca_config = session.execute(
        text("SELECT frequency, day FROM dca_strategies WHERE user_id = :uid AND active = TRUE"),
        {"uid": user_id},
    ).fetchone()

    if dca_config and buys:
        # Calcular precio medio real
        total_btc = sum(op.cantidad for op in buys)
        total_costo = sum(op.cantidad * op.precio + op.comision for op in buys)
        real_avg = total_costo / total_btc if total_btc > 0 else 0

        # Calcular precio medio DCA (aproximado)
        first_date = ops[0].fecha
        today = datetime.now().date()
        dca_prices = []
        current = today - timedelta(days=365)  # último año
        while current <= today:
            if price_map.get(current.isoformat()):
                dca_prices.append(price_map[current.isoformat()])
            current += timedelta(days=1)

        if dca_prices:
            dca_avg = sum(dca_prices) / len(dca_prices)
            diff_pct = (dca_avg - real_avg) / dca_avg * 100

            if abs(diff_pct) > 5:
                _crear_notification(
                    session, user_id,
                    notif_type="avg_price_vs_market",
                    title="💰 Precio medio vs promedio de mercado",
                    message=(
                        f"Tu precio medio (${real_avg:,.0f}) es "
                        f"{'menor' if diff_pct > 0 else 'mayor'} que el "
                        f"precio promedio del mercado en el último año "
                        f"(${dca_avg:,.0f}) por {abs(diff_pct):.0f}%. "
                        f"{'Buen timing de compras' if diff_pct > 0 else 'Considerá comprar más seguido para mejorar tu precio medio'}."
                    ),
                )


def _crear_notification(
    session: Session, user_id: int,
    notif_type: str, title: str, message: str,
    target_value: float = None, current_price: float = None,
):
    """Crea una notificación evitando duplicados recientes (últimas 24h del mismo tipo)."""
    from datetime import datetime as dt

    # Evitar duplicados: buscar si ya existe una notificación del mismo tipo en las últimas 6h
    existing = session.execute(
        text("""
            SELECT id FROM notifications
            WHERE user_id = :uid
              AND notif_type = :ntype
              AND created_at > :cutoff
            LIMIT 1
        """),
        {
            "uid": user_id,
            "ntype": notif_type,
            "cutoff": dt.utcnow() - timedelta(hours=6),
        },
    ).fetchone()

    if existing:
        logger.debug("Notificación %s ya existe para user %s (saltando)", notif_type, user_id)
        return

    session.execute(
        text("""
            INSERT INTO notifications (user_id, title, message, notif_type, target_value, current_price, read, created_at)
            VALUES (:uid, :title, :msg, :ntype, :tv, :cp, FALSE, :now)
        """),
        {
            "uid": user_id,
            "title": title,
            "msg": message,
            "ntype": notif_type,
            "tv": target_value,
            "cp": current_price,
            "now": dt.utcnow(),
        },
    )

    logger.info("🔔 Notificación %s creada para user %s", notif_type, user_id)
