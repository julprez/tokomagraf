# =============================================================
# intelligence_engine.py — Motor de Análisis Inteligente
# =============================================================
#
# Analiza las decisiones del usuario frente a la estrategia DCA
# y genera observaciones en lenguaje natural sobre:
#
# - Compras en caídas (timing)
# - Ventas prematuras (oportunidad perdida)
# - Mejora del precio medio
# - Hold vs trade (rentabilidad de mantener)
# - Conversiones a USDC (riesgo vs rentabilidad)
#

import logging
from datetime import date, timedelta, datetime
from typing import Optional

from app.models.models import Operation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("tokomagraf_api")


async def analyze_decisions(
    user_id: int,
    db: AsyncSession,
    price_map: dict[str, float],
    dca_purchases: list[dict],
    dca_invested: float,
    dca_btc: float,
    dca_pnl: float,
    dca_pnl_pct: float,
) -> dict:
    """
    Analiza las decisiones del usuario comparándolas con la estrategia DCA.

    Retorna un dict con:
      - observations: lista de observaciones en lenguaje natural
      - summary_parts: lista de fragmentos para el resumen general
      - timing_score: puntuación de timing (-100 a +100)
      - buy_quality: calidad de las compras (-100 a +100)
      - sell_impact: impacto de las ventas en la rentabilidad
    """
    from datetime import date as _dt

    obs: list[dict] = []
    today = _dt.today()

    # ── Obtener todas las operaciones ──
    result = await db.execute(
        select(Operation)
        .where(Operation.user_id == user_id)
        .order_by(Operation.fecha.asc())
    )
    all_ops = result.scalars().all()

    if not all_ops:
        return {"observations": [], "summary": "No hay suficientes datos para analizar.", "timing_score": 0, "buy_quality": 0, "sell_impact": 0}

    buys_btc = [op for op in all_ops if op.tipo == "buy" and op.activo == "BTC"]
    sells_btc = [op for op in all_ops if op.tipo == "sell" and op.activo == "BTC"]
    buys_usdc = [op for op in all_ops if op.tipo == "buy" and op.activo == "USDC"]
    deposits = [op for op in all_ops if op.tipo == "deposit"]

    # ── PRECIO MEDIO DE REFERENCIA ──
    # Calcular SMA 50 como proxy de tendencia
    precio_ref = _calcular_sma50(price_map, today)

    # ── 1. ANÁLISIS DE COMPRAS EN CAÍDAS ──
    buy_quality_score = 0
    total_buy_impact = 0
    compras_en_caida = []
    compras_en_maximos = []

    precio_actual = price_map.get(today.isoformat(), 0)

    for op in buys_btc:
        precio_op = op.precio
        fecha_key = op.fecha.isoformat()[:10] if op.fecha else ""

        # Encontrar precio 7 días antes de la compra para medir caída
        precio_7d_antes = _price_days_before(price_map, fecha_key, 7)
        precio_30d_antes = _price_days_before(price_map, fecha_key, 30)
        precio_7d_despues = _price_days_before(price_map, fecha_key, -7)

        caida_7d = ((precio_op - precio_7d_antes) / precio_7d_antes * 100) if precio_7d_antes else 0
        caida_30d = ((precio_op - precio_30d_antes) / precio_30d_antes * 100) if precio_30d_antes else 0
        cambio_7d_post = ((precio_7d_despues - precio_op) / precio_op * 100) if precio_7d_despues else 0

        # ¿Compró en caída?
        if caida_7d < -5:
            compras_en_caida.append({
                "fecha": fecha_key,
                "caida_7d": round(caida_7d, 1),
                "precio": round(precio_op, 2),
                "cantidad": op.cantidad,
            })
            if caida_7d < -10:
                buy_quality_score += 3
            else:
                buy_quality_score += 1

        # ¿Compró cerca de máximos recientes?
        high_30d = _max_price_in_window(price_map, fecha_key, 30)
        if high_30d and precio_op >= high_30d * 0.97:
            compras_en_maximos.append({
                "fecha": fecha_key,
                "precio": round(precio_op, 2),
                "high_30d": round(high_30d, 2),
            })
            buy_quality_score -= 2

        # ¿La compra fue rentable a los 7 días?
        if cambio_7d_post > 3 and caida_7d < -3:
            buy_quality_score += 2  # Bonus por comprar en caída que se recuperó
        elif cambio_7d_post < -5:
            buy_quality_score -= 1  # Penalty por comprar antes de una caída

    # ── 2. ANÁLISIS DE VENTAS PREMATURAS ──
    sell_impact_score = 0
    ventas_prematuras = []
    ventas_acertadas = []
    total_btc_vendido = 0.0
    pnl_perdido_ventas = 0.0

    for op in sells_btc:
        fecha_key = op.fecha.isoformat()[:10] if op.fecha else ""
        precio_venta = op.precio
        cantidad = op.cantidad
        total_btc_vendido += cantidad

        # Precio 30 días después de la venta
        precio_30d_post = _price_days_before(price_map, fecha_key, -30)

        if precio_30d_post:
            cambio_post = (precio_30d_post - precio_venta) / precio_venta * 100

            if cambio_post > 10:
                # Venta prematura: perdió subida
                perdida_estimada = cantidad * (precio_30d_post - precio_venta)
                pnl_perdido_ventas += perdida_estimada
                ventas_prematuras.append({
                    "fecha": fecha_key,
                    "cantidad": cantidad,
                    "precio_venta": round(precio_venta, 2),
                    "precio_30d": round(precio_30d_post, 2),
                    "cambio_pct": round(cambio_post, 1),
                    "perdida_estimada": round(perdida_estimada, 2),
                })
                sell_impact_score -= 2
            elif cambio_post < -5:
                # Venta acertada: evitó caída
                ventas_acertadas.append({
                    "fecha": fecha_key,
                    "cantidad": cantidad,
                    "precio_venta": round(precio_venta, 2),
                    "cambio_pct": round(cambio_post, 1),
                })
                sell_impact_score += 1

    # ── 3. COMPARATIVA DE PRECIO MEDIO ──
    avg_price_analysis = ""
    if buys_btc:
        # Precio medio real (ponderado por cantidad)
        total_btc_bought = sum(op.cantidad for op in buys_btc)
        total_btc_cost = sum(op.cantidad * op.precio + op.comision for op in buys_btc)
        real_avg = total_btc_cost / total_btc_bought if total_btc_bought > 0 else 0

        # Precio medio DCA
        if dca_purchases:
            dca_total_btc = sum(p["btc"] for p in dca_purchases)
            dca_avg = dca_invested / dca_total_btc if dca_total_btc > 0 else 0
        else:
            dca_avg = 0

        diff_avg = ((dca_avg - real_avg) / dca_avg * 100) if dca_avg > 0 else 0

        if diff_avg > 5:
            avg_price_analysis = (
                f"Tu precio medio (${real_avg:,.0f}) es un {abs(diff_avg):.1f}% "
                f"menor que el del DCA (${dca_avg:,.0f}). "
                f"Compraste en mejores momentos que el promedio, "
                f"lo que te da una ventaja de ${dca_avg - real_avg:,.0f} por BTC."
            )
        elif diff_avg < -5:
            avg_price_analysis = (
                f"Tu precio medio (${real_avg:,.0f}) es un {abs(diff_avg):.1f}% "
                f"mayor que el del DCA (${dca_avg:,.0f}). "
                f"El DCA habría conseguido un mejor precio promedio."
            )
        else:
            avg_price_analysis = (
                f"Tu precio medio (${real_avg:,.0f}) es similar "
                f"al del DCA (${dca_avg:,.0f}). "
                f"Tus compras están alineadas con el promedio del mercado."
            )

    # ── 4. ANÁLISIS HOLD VS TRADE ──
    hold_vs_trade = ""
    if sells_btc and precio_actual > 0:
        btc_vendido_total = sum(op.cantidad for op in sells_btc)
        if btc_vendido_total > 0:
            valor_actual_btc_vendido = btc_vendido_total * precio_actual
            ingresos_ventas = sum(op.cantidad * op.precio - op.comision for op in sells_btc)
            perdida_hold = valor_actual_btc_vendido - ingresos_ventas

            if perdida_hold > 0:
                hold_vs_trade = (
                    f"Si hubieras mantenido los {btc_vendido_total:.6f} BTC que vendiste, "
                    f"hoy valdrían ${valor_actual_btc_vendido:,.2f} en vez de los "
                    f"${ingresos_ventas:,.2f} que obtuviste. "
                    f"Dejaste de ganar ${perdida_hold:,.2f} por las ventas."
                )
            else:
                hold_vs_trade = (
                    f"Las ventas te permitieron capturar ${abs(perdida_hold):,.2f} "
                    f"que habrías perdido si mantenías."
                )

    # ── 5. CONVERSIONES A USDC ──
    usdc_analysis = ""
    if buys_usdc:
        total_usdc_comprado = sum(op.cantidad for op in buys_usdc)
        total_usdc_invertido = sum(op.cantidad * op.precio + op.comision for op in buys_usdc)
        usdc_analysis = (
            f"Compraste ${total_usdc_comprado:,.2f} en USDC "
            f"(${total_usdc_invertido:,.2f} invertidos). "
            f"El USDC actúa como reserva de valor frente a la volatilidad de BTC."
        )

    # ── 6. GENERAR OBSERVACIONES ESTRUCTURADAS ──
    observations = []

    if compras_en_caida:
        mejores = sorted(compras_en_caida, key=lambda x: x["caida_7d"])[:3]
        fechas_str = ", ".join(m["fecha"] for m in mejores)
        observations.append({
            "type": "buy_dip",
            "icon": "📉",
            "title": "Compraste en caídas",
            "detail": (
                f"Identificamos {len(compras_en_caida)} compra(s) durante caídas "
                f"del {abs(mejores[0]['caida_7d']):.0f}% o más en los 7 días anteriores. "
                f"Fechas destacadas: {fechas_str}."
            ),
            "impact": "positive",
            "score_impact": buy_quality_score,
        })

    if compras_en_maximos:
        observations.append({
            "type": "buy_high",
            "icon": "📈",
            "title": "Compraste cerca de máximos",
            "detail": (
                f"Realizaste {len(compras_en_maximos)} compra(s) cuando el precio "
                f"estaba cerca de máximos de 30 días. "
                f"Considerar esperar correcciones puede mejorar el precio medio."
            ),
            "impact": "negative",
            "score_impact": -len(compras_en_maximos),
        })

    if ventas_prematuras:
        peor_venta = max(ventas_prematuras, key=lambda x: x["perdida_estimada"])
        observations.append({
            "type": "sell_early",
            "icon": "😤",
            "title": "Ventas prematuras",
            "detail": (
                f"De tus {len(sells_btc)} venta(s), {len(ventas_prematuras)} resultaron prematuras: "
                f"el BTC subió >10% en los 30 días siguientes. "
                f"La venta más costosa fue el {peor_venta['fecha']}: "
                f"vendiste a ${peor_venta['precio_venta']:,.0f} y a los 30 días "
                f"cotizaba a ${peor_venta['precio_30d']:,.0f} (+{peor_venta['cambio_pct']:.0f}%). "
                f"Esto te costó aproximadamente ${peor_venta['perdida_estimada']:,.2f} en ganancias no realizadas."
            ),
            "impact": "negative",
            "score_impact": sell_impact_score,
        })

    if ventas_acertadas:
        observations.append({
            "type": "sell_good",
            "icon": "✅",
            "title": "Ventas acertadas",
            "detail": (
                f"De tus {len(sells_btc)} venta(s), {len(ventas_acertadas)} fueron acertadas: "
                f"el BTC cayó >5% en los 30 días siguientes, "
                f"lo que sugiere buen timing en esas decisiones."
            ),
            "impact": "positive",
            "score_impact": len(ventas_acertadas),
        })

    if avg_price_analysis:
        observations.append({
            "type": "avg_price",
            "icon": "💰",
            "title": "Precio medio vs DCA",
            "detail": avg_price_analysis,
            "impact": "positive" if "mejor" in avg_price_analysis or "similar" in avg_price_analysis else "negative",
            "score_impact": 0,
        })

    if hold_vs_trade:
        observations.append({
            "type": "hold",
            "icon": "🤲",
            "title": "Hold vs Trade",
            "detail": hold_vs_trade,
            "impact": "negative" if "dejaste de ganar" in hold_vs_trade else "positive",
            "score_impact": 0,
        })

    if usdc_analysis:
        observations.append({
            "type": "usdc",
            "icon": "💵",
            "title": "Exposición a USDC",
            "detail": usdc_analysis,
            "impact": "neutral",
            "score_impact": 0,
        })

    # ── 7. RESUMEN GENERAL ──
    summary_parts = []

    if dca_pnl_pct > 0 and dca_pnl_pct < 5:
        summary_parts.append("El mercado está plano.") if dca_pnl_pct < 2 else summary_parts.append("El DCA muestra una rentabilidad modesta, reflejando un mercado lateral.")

    if buy_quality_score > 5:
        summary_parts.append(f"Tus compras tienen buena calidad (puntuación {buy_quality_score}): tiendes a comprar en caídas, lo que mejora tu precio medio.")
    elif buy_quality_score < -2:
        summary_parts.append(f"Tus compras podrían mejorar (puntuación {buy_quality_score}): varias se realizaron cerca de máximos o antes de correcciones.")

    if sell_impact_score < -3:
        summary_parts.append(f"Las ventas redujeron tu rentabilidad (impacto {sell_impact_score}). El DCA nunca vende, y mantener posiciones hubiera sido más rentable en retrospectiva.")
    elif sell_impact_score > 0:
        summary_parts.append(f"Tus ventas fueron en su mayoría acertadas (impacto {sell_impact_score}), mostrando buen timing para tomar ganancias o reducir riesgo.")

    # Puntuación general de timing (-100 a +100)
    timing_score = max(-100, min(100, buy_quality_score * 5 + sell_impact_score * 3))

    summary = " ".join(summary_parts) if summary_parts else "No se detectaron patrones significativos en tus operaciones."

    return {
        "observations": observations,
        "summary": summary,
        "timing_score": timing_score,
        "buy_quality": buy_quality_score,
        "sell_impact": sell_impact_score,
        "buy_dip_count": len(compras_en_caida),
        "sell_premature_count": len(ventas_prematuras),
        "sell_good_count": len(ventas_acertadas),
        "total_btc_sold": round(total_btc_vendido, 8),
        "pnl_lost_from_sells": round(pnl_perdido_ventas, 2),
    }


def _calcular_sma50(price_map: dict[str, float], today: date) -> Optional[float]:
    """Calcula SMA 50 desde los precios disponibles."""
    fechas = sorted(price_map.keys())
    precios_recientes = []
    for f in reversed(fechas):
        if len(precios_recientes) >= 50:
            break
        precios_recientes.append(price_map[f])
    if len(precios_recientes) < 10:
        return None
    return sum(precios_recientes) / len(precios_recientes)


def _price_days_before(price_map: dict[str, float], fecha: str, days: int) -> Optional[float]:
    """Obtiene el precio N días antes (days positivo) o después (days negativo) de una fecha."""
    from datetime import date as _dt, timedelta as _td
    try:
        d = _dt.fromisoformat(fecha)
        target = d + _td(days=days)
        return price_map.get(target.isoformat())
    except (ValueError, KeyError):
        return None


def _max_price_in_window(price_map: dict[str, float], fecha: str, window_days: int) -> Optional[float]:
    """Encuentra el precio máximo en una ventana de días."""
    from datetime import date as _dt, timedelta as _td
    try:
        d = _dt.fromisoformat(fecha)
        prices = []
        for i in range(window_days):
            target = (d - _td(days=i)).isoformat()
            if target in price_map:
                prices.append(price_map[target])
        return max(prices) if prices else None
    except (ValueError, KeyError):
        return None
