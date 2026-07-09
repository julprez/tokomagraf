# =============================================================
# dca_simulator.py — Motor de simulación DCA
# =============================================================
#
# Reconstruye una cartera DCA (Dollar-Cost Averaging) simulada
# desde la primera operación real del usuario hasta hoy.
#
# La DCA invierte el MISMO capital total que el usuario invirtió,
# pero distribuido en montos iguales a intervalos regulares.
# Nunca vende (salvo que el usuario venda en su cartera real).
#

import logging
import time
from datetime import date, timedelta, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Operation, DailyHistory, DcaStrategy, User
from app.services.price_service import fetch_btc_chart, fetch_btc_price
from app.services.intelligence_engine import analyze_decisions

logger = logging.getLogger("tokomagraf_api")

# ── Caché DCA ──
_dca_cache: dict[int, tuple[float, dict]] = {}
_DCA_CACHE_TTL = 300  # 5 minutos


def invalidate_dca_cache(user_id: int) -> None:
    """Invalida el caché DCA para un usuario (ej: después de nueva operación)."""
    _dca_cache.pop(user_id, None)


async def simulate_dca(user_id: int, db: AsyncSession) -> Optional[dict]:
    # Verificar caché
    cached = _dca_cache.get(user_id)
    if cached:
        ts, data = cached
        if time.monotonic() - ts < _DCA_CACHE_TTL:
            logger.debug("DCA cache hit for user %d", user_id)
            return data
    logger.debug("DCA cache miss for user %d", user_id)
    """
    Simula la cartera DCA y la compara con la cartera real.

    Retorna:
      - config: configuración DCA actual
      - real: métricas de la cartera real
      - dca: métricas de la cartera DCA simulada
      - comparacion: diferencias entre ambas
      - charts: datasets para gráficos (real, dca, diferencia, btc_acumulado)
    """
    # ── Obtener configuración DCA del usuario ──
    result = await db.execute(
        select(DcaStrategy).where(DcaStrategy.user_id == user_id)
    )
    strategy = result.scalar_one_or_none()

    # Si no tiene estrategia, crear una por defecto
    if not strategy:
        strategy = DcaStrategy(user_id=user_id, frequency="weekly", day=1)
        db.add(strategy)
        await db.commit()
        await db.refresh(strategy)

    # ── Obtener operaciones reales ──
    ops_result = await db.execute(
        select(Operation)
        .where(Operation.user_id == user_id)
        .order_by(Operation.fecha.asc())
    )
    all_ops = ops_result.scalars().all()

    if not all_ops:
        return None

    # ── Calcular capital total invertido real ──
    total_capital = 0.0
    for op in all_ops:
        if op.tipo == "buy":
            total_capital += op.cantidad * op.precio + op.comision
        elif op.tipo == "deposit":
            total_capital += op.cantidad

    # ── Fecha de inicio = primera operación ──
    first_op_date = all_ops[0].fecha
    start_date = first_op_date.date() if hasattr(first_op_date, 'date') else first_op_date
    today = date.today()

    # ── Obtener historial BTC para el período ──
    # CoinGecko free API solo soporta hasta ~365 días en /market_chart
    days_span = (today - start_date).days + 30
    days_span = max(30, min(365, days_span))  # CoinGecko free limit

    # Fallback progresivo: intentar con days_span, luego 365, 90, 30
    btc_chart = None
    for try_days in [days_span, 365, 90, 30]:
        chart = await fetch_btc_chart(try_days)
        if chart and len(chart) >= 2:
            btc_chart = chart
            logger.info("DCA: obtuve chart de %d días para user %d", try_days, user_id)
            break
        logger.warning("DCA: chart de %d días falló para user %d", try_days, user_id)

    if not btc_chart or len(btc_chart) < 2:
        logger.error("DCA: no se pudo obtener ningún chart BTC para user %d", user_id)
        return None

    # Indexar precios por fecha (aproximación: el chart tiene 1 punto cada ~2h)
    price_map: dict[str, float] = {}
    for entry in btc_chart:
        ts_ms = entry.get("timestamp", 0)
        dt = datetime.fromtimestamp(ts_ms / 1000)
        fecha_key = dt.date().isoformat()
        if fecha_key not in price_map:
            price_map[fecha_key] = entry["price"]

    # Obtener precio actual
    current_price_data = await fetch_btc_price()
    btc_price_now = current_price_data["price_usd"] if current_price_data else price_map.get(today.isoformat(), 0)

    # ── Generar calendario de compras DCA ──
    dca_purchases = _generate_dca_schedule(start_date, today, total_capital, strategy, price_map)

    # ── Calcular cartera DCA simulada ──
    dca_btc = 0.0
    dca_invested = 0.0
    dca_daily_history: list[dict] = []

    for purchase in dca_purchases:
        dca_btc += purchase["btc"]
        dca_invested += purchase["amount"]
        dca_daily_history.append({
            "fecha": purchase["fecha"],
            "btc": round(dca_btc, 8),
            "invertido": round(dca_invested, 2),
            "compra": round(purchase["amount"], 2),
            "precio": round(purchase["precio"], 2),
        })

    # Si no hay compras DCA (caso borde), retornar None
    if not dca_daily_history:
        return None

    # ── Calcular métricas DCA actuales ──
    dca_valor = round(dca_btc * btc_price_now, 2)
    dca_pnl = round(dca_valor - dca_invested, 2)
    dca_pnl_pct = round((dca_pnl / dca_invested * 100), 2) if dca_invested > 0 else 0.0
    dca_avg_price = round(dca_invested / dca_btc, 2) if dca_btc > 0 else 0

    # ── Calcular métricas reales actuales ──
    real_btc = 0.0
    real_invested = 0.0
    real_usdc = 0.0
    real_total_btc_cost = 0.0

    for op in all_ops:
        if op.tipo == "buy":
            if op.activo == "BTC":
                real_btc += op.cantidad
                real_total_btc_cost += op.cantidad * op.precio + op.comision
                real_invested += op.cantidad * op.precio + op.comision
            elif op.activo == "USDC":
                real_invested += op.cantidad * op.precio + op.comision
        elif op.tipo == "sell" and op.activo == "BTC":
            real_btc -= op.cantidad
            if real_btc < 0:
                real_btc = 0.0
        elif op.tipo == "deposit":
            real_invested += op.cantidad
            if op.activo == "USDC":
                real_usdc += op.cantidad

    real_valor = round(real_btc * btc_price_now + real_usdc, 2)
    real_pnl = round(real_valor - real_invested, 2)
    real_pnl_pct = round((real_pnl / real_invested * 100), 2) if real_invested > 0 else 0.0
    real_avg_price = round(real_total_btc_cost / real_btc, 2) if real_btc > 0 else 0

    # ── Generar datasets de evolución diaria para comparación ──
    # Reconstruir evolución real día a día
    real_daily = await _get_real_daily_evolution(user_id, db, btc_price_now)

    # Evolución DCA diaria con valor actualizado a precio BTC
    dca_daily_value = []
    for entry in dca_daily_history:
        # Estimar precio BTC en esa fecha
        precio_btc = price_map.get(entry["fecha"], btc_price_now)
        valor = round(entry["btc"] * precio_btc, 2)
        dca_daily_value.append({
            "fecha": entry["fecha"],
            "valor": valor,
            "btc": entry["btc"],
            "invertido": entry["invertido"],
        })

    # Agregar punto actual
    dca_daily_value.append({
        "fecha": today.isoformat(),
        "valor": dca_valor,
        "btc": round(dca_btc, 8),
        "invertido": round(dca_invested, 2),
    })

    # ── Diferencia acumulada ──
    # Alinear fechas entre real y DCA para calcular diferencia
    fechas_dca = {e["fecha"] for e in dca_daily_value}
    diferencia = []
    for entry_real in real_daily:
        fecha = entry_real["fecha"]
        if fecha in fechas_dca:
            dca_entry = next(e for e in dca_daily_value if e["fecha"] == fecha)
            diff = round(entry_real["valor"] - dca_entry["valor"], 2)
            diferencia.append({
                "fecha": fecha,
                "diferencia": diff,
                "real": entry_real["valor"],
                "dca": dca_entry["valor"],
            })

    # ── BTC acumulados (ambas carteras) ──
    btc_acumulado = []
    fechas_todas = sorted(set(e["fecha"] for e in real_daily) | fechas_dca)
    for fecha in fechas_todas:
        real_b = next((e["btc"] for e in real_daily if e["fecha"] == fecha), None)
        dca_b = next((e["btc"] for e in dca_daily_value if e["fecha"] == fecha), None)
        if real_b is not None or dca_b is not None:
            btc_acumulado.append({
                "fecha": fecha,
                "real_btc": real_b or 0,
                "dca_btc": dca_b or 0,
            })

    # ── Métricas adicionales ──
    # Coste medio
    real_avg_price = round(real_total_btc_cost / real_btc, 2) if real_btc > 0 else 0
    dca_avg_price = round(dca_invested / dca_btc, 2) if dca_btc > 0 else 0

    # Conteo de operaciones
    real_buys = sum(1 for op in all_ops if op.tipo == "buy" and op.activo == "BTC")
    real_sells = sum(1 for op in all_ops if op.tipo == "sell" and op.activo == "BTC")

    # Ganancia media por operación
    real_avg_trade_pnl = round(real_pnl / (real_buys + real_sells), 2) if (real_buys + real_sells) > 0 else 0

    # Drawdown (aproximado desde daily_history real)
    real_drawdown = await _calculate_max_drawdown(user_id, db)

    # DCA drawdown (desde valores simulados)
    dca_drawdown = _calculate_drawdown_from_series(dca_daily_value)

    # ── Motor de Inteligencia ──
    try:
        intelligence = await analyze_decisions(
            user_id=user_id,
            db=db,
            price_map=price_map,
            dca_purchases=dca_purchases,
            dca_invested=dca_invested,
            dca_btc=dca_btc,
            dca_pnl=dca_pnl,
            dca_pnl_pct=dca_pnl_pct,
        )
    except Exception as e:
        logger.error("Error en motor de inteligencia: %s", e)
        intelligence = {
            "observations": [],
            "summary": "El análisis inteligente no está disponible temporalmente.",
            "timing_score": 0,
        }

    result = {
        "intelligence": intelligence,
        "config": {
            "frequency": strategy.frequency,
            "day": strategy.day,
            "active": strategy.active,
        },
        "real": {
            "capital_invertido": round(real_invested, 2),
            "btc_acumulado": round(real_btc, 8),
            "valor_actual": real_valor,
            "beneficio": real_pnl,
            "rentabilidad_pct": real_pnl_pct,
            "coste_medio": real_avg_price,
            "num_compras": real_buys,
            "num_ventas": real_sells,
            "ganancia_media_por_operacion": real_avg_trade_pnl,
            "max_drawdown_pct": real_drawdown,
        },
        "dca": {
            "capital_invertido": round(dca_invested, 2),
            "btc_acumulado": round(dca_btc, 8),
            "valor_actual": dca_valor,
            "beneficio": dca_pnl,
            "rentabilidad_pct": dca_pnl_pct,
            "coste_medio": dca_avg_price,
            "num_compras": len(dca_purchases),
            "num_ventas": 0,
            "ganancia_media_por_operacion": round(dca_pnl / len(dca_purchases), 2) if dca_purchases else 0,
            "max_drawdown_pct": dca_drawdown,
        },
        "comparacion": {
            "diferencia_beneficio": round(real_pnl - dca_pnl, 2),
            "diferencia_rentabilidad_pct": round(real_pnl_pct - dca_pnl_pct, 2),
            "diferencia_btc": round(real_btc - dca_btc, 8),
            "diferencia_coste_medio": round(real_avg_price - dca_avg_price, 2),
            "ganador": "real" if real_pnl > dca_pnl else "dca" if dca_pnl > real_pnl else "empate",
            "resumen": _generar_resumen(real_pnl, dca_pnl, real_pnl_pct, dca_pnl_pct, real_buys, real_sells),
        },
        "charts": {
            "evolucion_real": real_daily,
            "evolucion_dca": dca_daily_value,
            "diferencia": diferencia,
            "btc_acumulado": btc_acumulado,
        },
    }

    # Guardar en caché
    _dca_cache[user_id] = (time.monotonic(), result)
    return result


def _generate_dca_schedule(
    start_date: date, end_date: date, total_capital: float,
    strategy: DcaStrategy, price_map: dict[str, float],
) -> list[dict]:
    """Genera el calendario de compras DCA y las simula."""
    frequency = strategy.frequency or "weekly"
    day = strategy.day or 1

    purchases = []
    current = start_date
    dates = []

    if frequency == "weekly":
        # Avanzar al primer día de la semana especificado
        while current.weekday() != day:
            current += timedelta(days=1)
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=7)
    else:  # monthly
        safe_day = min(day, 28)  # Protección contra días > 28 (ej: febrero)
        # Ir al día del mes especificado
        if current.day > safe_day:
            # Ir al próximo mes
            month = current.month + 1
            year = current.year
            if month > 12:
                month = 1
                year += 1
            try:
                current = date(year, month, safe_day)
            except ValueError:
                current = date(year, month, 28)
        else:
            try:
                current = date(current.year, current.month, safe_day)
            except ValueError:
                current = date(current.year, current.month, 1)

        while current <= end_date:
            dates.append(current)
            # Avanzar un mes
            month = current.month + 1
            year = current.year
            if month > 12:
                month = 1
                year += 1
            try:
                current = date(year, month, safe_day)
            except ValueError:
                current = date(year, month, 28)

    # Si no se generaron fechas, forzar al menos una compra en start_date
    if not dates:
        dates = [start_date]

    if not dates:
        return []

    # Monto por compra
    amount_per_purchase = round(total_capital / len(dates), 2)

    # Simular cada compra
    for d in dates:
        fecha_key = d.isoformat()
        btc_price = price_map.get(fecha_key)

        # Si no hay precio para esa fecha exacta, buscar el más cercano anterior
        if btc_price is None:
            # Buscar hasta 7 días antes
            for offset in range(1, 8):
                prev = (d - timedelta(days=offset)).isoformat()
                if prev in price_map:
                    btc_price = price_map[prev]
                    break

        if btc_price is None or btc_price <= 0:
            continue

        btc_bought = round(amount_per_purchase / btc_price, 8)
        purchases.append({
            "fecha": fecha_key,
            "amount": amount_per_purchase,
            "precio": btc_price,
            "btc": btc_bought,
        })

    return purchases


async def _get_real_daily_evolution(user_id: int, db: AsyncSession, btc_price_now: float) -> list[dict]:
    """Reconstruye la evolución diaria real de la cartera."""
    from datetime import date as _dt
    today = _dt.today()
    result = await db.execute(
        select(DailyHistory)
        .where(DailyHistory.user_id == user_id)
        .order_by(DailyHistory.fecha.asc())
    )
    daily = result.scalars().all()

    if not daily:
        return [{"fecha": today.isoformat(), "valor": 0, "btc": 0, "invertido": 0}]

    evolution = []
    for h in daily:
        evolution.append({
            "fecha": h.fecha.isoformat(),
            "valor": round(h.valor_portfolio, 2),
            "btc": round(h.btc, 8),
            "usdc": round(h.usdc, 2),
        })

    return evolution


async def _calculate_max_drawdown(user_id: int, db: AsyncSession) -> Optional[float]:
    """Calcula el máximo drawdown desde el historial diario real."""
    result = await db.execute(
        select(DailyHistory)
        .where(DailyHistory.user_id == user_id)
        .order_by(DailyHistory.fecha.asc())
    )
    daily = result.scalars().all()
    if len(daily) < 2:
        return None

    peak = daily[0].valor_portfolio
    max_dd = 0.0
    for h in daily:
        if h.valor_portfolio > peak:
            peak = h.valor_portfolio
        dd = (peak - h.valor_portfolio) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


def _calculate_drawdown_from_series(series: list[dict]) -> Optional[float]:
    """Calcula máximo drawdown desde una serie de valores."""
    if len(series) < 2:
        return None
    peak = series[0]["valor"]
    max_dd = 0.0
    for entry in series:
        val = entry["valor"]
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


def _generar_resumen(
    real_pnl: float, dca_pnl: float,
    real_pnl_pct: float, dca_pnl_pct: float,
    real_buys: int, real_sells: int,
) -> str:
    """Genera un resumen en lenguaje natural comparando ambas estrategias."""
    partes = []

    if real_pnl > dca_pnl:
        diff = real_pnl - dca_pnl
        diff_pct = real_pnl_pct - dca_pnl_pct
        partes.append(
            f"Tu estrategia supera al DCA por ${diff:+.2f} "
            f"({diff_pct:+.2f} puntos porcentuales)."
        )
    elif dca_pnl > real_pnl:
        diff = dca_pnl - real_pnl
        diff_pct = dca_pnl_pct - real_pnl_pct
        partes.append(
            f"El DCA supera a tu estrategia por ${diff:+.2f} "
            f"({diff_pct:+.2f} puntos porcentuales)."
        )
    else:
        partes.append("Ambas estrategias tienen resultados equivalentes.")

    if real_sells > 0:
        partes.append(
            f"Realizaste {real_sells} venta(s), lo que puede haber afectado "
            f"la rentabilidad respecto a mantener la posición."
        )
    else:
        partes.append("No realizaste ventas, similar a la estrategia DCA.")

    return " ".join(partes)
