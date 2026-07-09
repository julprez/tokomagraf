# =============================================================
# prediction_service.py — Sistema de Predicción/Puntuación
# =============================================================
#
# Servicio independiente que analiza múltiples indicadores
# y produce una puntuación unificada (0-100%) con motivos.
# NO realiza compras ni ventas automáticas.
#

import logging
from datetime import datetime, timezone
from typing import Optional

from app.services.price_service import (
    fetch_btc_price,
    fetch_btc_detail,
    fetch_btc_chart,
    fetch_fear_greed,
    fetch_btc_dominance,
    fetch_global_metrics,
)
from app.services.indicator_service import (
    calculate_rsi,
    calculate_macd,
    calculate_sma,
    calculate_ema,
    calculate_bollinger,
    calculate_atr,
    find_support_resistance,
)

logger = logging.getLogger("tokomagraf_api")

# ── Pesos de cada indicador en la puntuación final ──
WEIGHTS = {
    "rsi": 2.0,
    "macd": 1.5,
    "sma_trend": 1.5,
    "bollinger": 1.0,
    "support_resistance": 1.0,
    "volume": 0.5,
    "fear_greed": 1.5,
    "btc_dominance": 0.5,
    "price_position": 0.5,
}


async def compute_prediction() -> Optional[dict]:
    """
    Analiza todos los indicadores y produce una puntuación unificada.

    Retorna:
      - score: 0-100 (0 = máxima venta, 100 = máxima compra, 50 = neutral)
      - signal: "compra_fuerte" | "compra" | "neutral" | "venta" | "venta_fuerte"
      - reasons: lista de motivos con impacto positivo/negativo
      - details: valores actuales de cada indicador
    """
    # ── 1. Obtener datos ──
    price_data = await fetch_btc_price()
    detail_data = await fetch_btc_detail()
    chart_data = await fetch_btc_chart(90)
    fng = await fetch_fear_greed()
    global_metrics = await fetch_global_metrics()

    if not price_data or not chart_data or len(chart_data) < 30:
        return None

    prices = [d["price"] for d in chart_data]
    current_price = price_data["price_usd"]
    change_24h = price_data.get("change_24h")

    # ── 2. Calcular indicadores técnicos ──
    rsi_raw = calculate_rsi(prices, 14)
    macd_line, macd_signal, macd_hist = calculate_macd(prices)
    sma_50_raw = calculate_sma(prices, min(50, len(prices)))
    sma_200_raw = calculate_sma(prices, min(200, len(prices)))
    bb_upper, bb_mid, bb_lower = calculate_bollinger(prices)
    sr = find_support_resistance(prices)

    rsi = rsi_raw[-1] if rsi_raw and rsi_raw[-1] is not None else None
    sma_50 = sma_50_raw[-1] if sma_50_raw and sma_50_raw[-1] is not None else None
    sma_200 = sma_200_raw[-1] if sma_200_raw and sma_200_raw[-1] is not None else None

    macd_line_val = macd_line[-1] if macd_line and macd_line[-1] is not None else None
    macd_signal_val = macd_signal[-1] if macd_signal and macd_signal[-1] is not None else None
    macd_hist_val = macd_hist[-1] if macd_hist and macd_hist[-1] is not None else None

    bb_upper_val = bb_upper[-1] if bb_upper and bb_upper[-1] is not None else None
    bb_lower_val = bb_lower[-1] if bb_lower and bb_lower[-1] is not None else None
    bb_mid_val = bb_mid[-1] if bb_mid and bb_mid[-1] is not None else None

    volume_24h = detail_data.get("volume") if detail_data else None

    # ── 3. Evaluar cada indicador → puntuación parcial (0-100) ──
    reasons: list[dict] = []
    total_score = 50.0  # Parte de neutral
    total_weight = 0.0

    def add_signal(name: str, impact: float, weight: float, detail: str):
        """Agrega una señal. impact: -1 (muy bajista) a +1 (muy alcista)."""
        nonlocal total_score, total_weight
        score_delta = impact * 50  # escala a -50..+50
        total_score += score_delta * weight
        total_weight += weight

        if impact > 0.3:
            direction = "alcista"
        elif impact < -0.3:
            direction = "bajista"
        else:
            direction = "neutral"

        reasons.append({
            "indicator": name,
            "impact": round(impact, 2),
            "weight": weight,
            "direction": direction,
            "detail": detail,
        })

    # RSI
    if rsi is not None:
        if rsi < 25:
            add_signal("RSI", 0.9, WEIGHTS["rsi"], f"RSI en {rsi:.1f} — sobreventa extrema")
        elif rsi < 35:
            add_signal("RSI", 0.5, WEIGHTS["rsi"], f"RSI en {rsi:.1f} — cerca de sobreventa")
        elif rsi < 45:
            add_signal("RSI", 0.2, WEIGHTS["rsi"], f"RSI en {rsi:.1f} — ligeramente bajo")
        elif rsi > 75:
            add_signal("RSI", -0.9, WEIGHTS["rsi"], f"RSI en {rsi:.1f} — sobrecompra extrema")
        elif rsi > 65:
            add_signal("RSI", -0.5, WEIGHTS["rsi"], f"RSI en {rsi:.1f} — cerca de sobrecompra")
        elif rsi > 55:
            add_signal("RSI", -0.2, WEIGHTS["rsi"], f"RSI en {rsi:.1f} — ligeramente alto")
        else:
            add_signal("RSI", 0.0, WEIGHTS["rsi"], f"RSI en {rsi:.1f} — neutral")

    # MACD
    if macd_line_val is not None and macd_signal_val is not None:
        if macd_line_val > macd_signal_val and macd_hist_val is not None and macd_hist_val > 0:
            add_signal("MACD", 0.7, WEIGHTS["macd"], f"Línea MACD sobre señal con histograma positivo — cruce alcista")
        elif macd_line_val > macd_signal_val:
            add_signal("MACD", 0.3, WEIGHTS["macd"], "Línea MACD sobre señal — leve alcista")
        elif macd_line_val < macd_signal_val and macd_hist_val is not None and macd_hist_val < 0:
            add_signal("MACD", -0.7, WEIGHTS["macd"], f"Línea MACD bajo señal con histograma negativo — cruce bajista")
        elif macd_line_val < macd_signal_val:
            add_signal("MACD", -0.3, WEIGHTS["macd"], "Línea MACD bajo señal — leve bajista")
        else:
            add_signal("MACD", 0.0, WEIGHTS["macd"], "MACD neutral")

    # SMA — Tendencia (Golden/Death Cross)
    if sma_50 is not None and sma_200 is not None:
        diff_pct = (sma_50 - sma_200) / sma_200 * 100
        if diff_pct > 5:
            add_signal("Tendencia SMA", 0.8, WEIGHTS["sma_trend"],
                       f"SMA 50 ({sma_50:.0f}) muy sobre SMA 200 ({sma_200:.0f}) — tendencia alcista fuerte")
        elif diff_pct > 1:
            add_signal("Tendencia SMA", 0.4, WEIGHTS["sma_trend"],
                       f"Golden Cross: SMA 50 ({sma_50:.0f}) > SMA 200 ({sma_200:.0f})")
        elif diff_pct < -5:
            add_signal("Tendencia SMA", -0.8, WEIGHTS["sma_trend"],
                       f"SMA 50 ({sma_50:.0f}) muy bajo SMA 200 ({sma_200:.0f}) — tendencia bajista fuerte")
        elif diff_pct < -1:
            add_signal("Tendencia SMA", -0.4, WEIGHTS["sma_trend"],
                       f"Death Cross: SMA 50 ({sma_50:.0f}) < SMA 200 ({sma_200:.0f})")
        else:
            add_signal("Tendencia SMA", 0.0, WEIGHTS["sma_trend"],
                       f"SMA 50 ({sma_50:.0f}) y SMA 200 ({sma_200:.0f}) alineadas")
    elif sma_50 is not None:
        if current_price > sma_50 * 1.05:
            add_signal("Tendencia SMA", 0.3, WEIGHTS["sma_trend"],
                       f"Precio ${current_price:.0f} > SMA 50 ${sma_50:.0f}")
        elif current_price < sma_50 * 0.95:
            add_signal("Tendencia SMA", -0.3, WEIGHTS["sma_trend"],
                       f"Precio ${current_price:.0f} < SMA 50 ${sma_50:.0f}")

    # Bollinger Bands
    if bb_upper_val is not None and bb_lower_val is not None and bb_mid_val is not None:
        bb_width = (bb_upper_val - bb_lower_val) / bb_mid_val * 100
        if current_price <= bb_lower_val:
            add_signal("Bollinger", 0.6, WEIGHTS["bollinger"],
                       f"Precio en banda inferior (${bb_lower_val:.0f}) — posible soporte")
        elif current_price >= bb_upper_val:
            add_signal("Bollinger", -0.6, WEIGHTS["bollinger"],
                       f"Precio tocando banda superior (${bb_upper_val:.0f}) — posible resistencia")
        elif bb_width < 10:
            # Bandas estrechas = posible explosión
            pos_in_band = (current_price - bb_lower_val) / (bb_upper_val - bb_lower_val)
            if 0.3 < pos_in_band < 0.7:
                add_signal("Bollinger", 0.3, WEIGHTS["bollinger"],
                           f"Bandas estrechas ({bb_width:.1f}%) — posible expansión pronto")
            else:
                add_signal("Bollinger", 0.0, WEIGHTS["bollinger"],
                           f"Ancho de bandas: {bb_width:.1f}%")
        else:
            add_signal("Bollinger", 0.0, WEIGHTS["bollinger"], "Bandas dentro de rango normal")

    # Soporte y Resistencia
    if sr.get("support") and sr.get("resistance"):
        dist_support = (current_price - sr["support"]) / sr["support"] * 100
        dist_resistance = (sr["resistance"] - current_price) / current_price * 100
        near_support = dist_support < 2.0
        near_resistance = dist_resistance < 2.0

        if near_support:
            add_signal("Soporte/Resistencia", 0.5, WEIGHTS["support_resistance"],
                       f"Precio cerca de soporte en ${sr['support']:.0f} (a {dist_support:.1f}%)")
        elif near_resistance:
            add_signal("Soporte/Resistencia", -0.4, WEIGHTS["support_resistance"],
                       f"Precio cerca de resistencia en ${sr['resistance']:.0f} (a {dist_resistance:.1f}%)")
        elif dist_support < dist_resistance:
            add_signal("Soporte/Resistencia", 0.2, WEIGHTS["support_resistance"],
                       f"Más cerca de soporte (${sr['support']:.0f}) que de resistencia (${sr['resistance']:.0f})")
        else:
            add_signal("Soporte/Resistencia", -0.2, WEIGHTS["support_resistance"],
                       f"Más cerca de resistencia (${sr['resistance']:.0f}) que de soporte (${sr['support']:.0f})")

    # Precio vs MA200 (posición relativa)
    if sma_200 is not None:
        dist_ma200 = (current_price - sma_200) / sma_200 * 100
        if dist_ma200 > 20:
            add_signal("Posición precio", -0.3, WEIGHTS["price_position"],
                       f"Precio {dist_ma200:.0f}% sobre MA200 — extendido")
        elif dist_ma200 < -20:
            add_signal("Posición precio", 0.5, WEIGHTS["price_position"],
                       f"Precio {abs(dist_ma200):.0f}% bajo MA200 — posible rebote")
        elif dist_ma200 > 10:
            add_signal("Posición precio", -0.1, WEIGHTS["price_position"],
                       f"Precio {dist_ma200:.0f}% sobre MA200")
        elif dist_ma200 < -10:
            add_signal("Posición precio", 0.2, WEIGHTS["price_position"],
                       f"Precio {abs(dist_ma200):.0f}% bajo MA200")
        else:
            add_signal("Posición precio", 0.1, WEIGHTS["price_position"],
                       f"Precio cerca de MA200 ({dist_ma200:+.1f}%)")

    # Volumen 24h
    # Usamos el volumen como proxy de actividad: alto volumen confirma tendencia
    if volume_24h is not None and global_metrics and global_metrics.get("total_volume"):
        btc_volume = volume_24h
        total_crypto_volume = global_metrics["total_volume"]
        btc_volume_share = (btc_volume / total_crypto_volume * 100) if total_crypto_volume > 0 else 0

        # BTC volume > $20B = alta actividad
        if btc_volume > 30e9:
            add_signal("Volumen", 0.2, WEIGHTS["volume"],
                       f"Volumen BTC 24h ${btc_volume / 1e9:.2f}B — muy activo ({btc_volume_share:.1f}% del mercado)")
        elif btc_volume > 15e9:
            add_signal("Volumen", 0.1, WEIGHTS["volume"],
                       f"Volumen BTC 24h ${btc_volume / 1e9:.2f}B — actividad normal")
        elif btc_volume > 8e9:
            add_signal("Volumen", -0.1, WEIGHTS["volume"],
                       f"Volumen BTC 24h ${btc_volume / 1e9:.2f}B — bajo")
        else:
            add_signal("Volumen", -0.2, WEIGHTS["volume"],
                       f"Volumen BTC 24h ${btc_volume / 1e9:.2f}B — muy bajo, poca actividad")

    # Fear & Greed
    if fng:
        fng_val = fng["value"]
        fng_label = fng["classification"]
        if fng_val < 20:
            add_signal("Fear & Greed", 0.8, WEIGHTS["fear_greed"],
                       f"Índice en {fng_val} — Miedo Extremo ({fng_label})")
        elif fng_val < 40:
            add_signal("Fear & Greed", 0.4, WEIGHTS["fear_greed"],
                       f"Índice en {fng_val} — Miedo ({fng_label})")
        elif fng_val > 80:
            add_signal("Fear & Greed", -0.7, WEIGHTS["fear_greed"],
                       f"Índice en {fng_val} — Codicia Extrema ({fng_label})")
        elif fng_val > 60:
            add_signal("Fear & Greed", -0.3, WEIGHTS["fear_greed"],
                       f"Índice en {fng_val} — Codicia ({fng_label})")
        else:
            add_signal("Fear & Greed", 0.0, WEIGHTS["fear_greed"],
                       f"Índice en {fng_val} — Neutral ({fng_label})")

    # Dominancia BTC
    if global_metrics:
        dom = global_metrics["btc_dominance"]
        # Alta dominancia = altcoins débiles, BTC refugio
        # Baja dominancia = money rotando a alts, posible alt season
        if dom > 60:
            add_signal("Dominancia BTC", 0.3, WEIGHTS["btc_dominance"],
                       f"Dominancia BTC en {dom:.1f}% — muy alta, BTC como refugio")
        elif dom > 50:
            add_signal("Dominancia BTC", 0.1, WEIGHTS["btc_dominance"],
                       f"Dominancia BTC en {dom:.1f}% — ligeramente alta")
        elif dom < 38:
            add_signal("Dominancia BTC", -0.2, WEIGHTS["btc_dominance"],
                       f"Dominancia BTC en {dom:.1f}% — baja, dinero rotando a alts")
        else:
            add_signal("Dominancia BTC", 0.0, WEIGHTS["btc_dominance"],
                       f"Dominancia BTC en {dom:.1f}% — neutral")

    # ── 4. Calcular puntuación final ──
    final_score = total_score / (total_weight / sum(WEIGHTS.values())) if total_weight > 0 else 50
    final_score = max(0, min(100, final_score))  # Clampear a 0-100

    # Clasificar señal
    if final_score >= 75:
        signal = "compra_fuerte"
    elif final_score >= 60:
        signal = "compra"
    elif final_score >= 40:
        signal = "neutral"
    elif final_score >= 25:
        signal = "venta"
    else:
        signal = "venta_fuerte"

    # Ordenar motivos por impacto absoluto
    reasons.sort(key=lambda r: abs(r["impact"]) * r["weight"], reverse=True)

    # Calcular cambio de precio (soporte más cercano vs precio actual)
    upside = None
    downside = None
    if sr.get("support") and sr.get("resistance"):
        upside = round((sr["resistance"] - current_price) / current_price * 100, 1) if sr["resistance"] else None
        downside = round((current_price - sr["support"]) / current_price * 100, 1) if sr["support"] else None

    return {
        "score": round(final_score, 1),
        "signal": signal,
        "current_price": current_price,
        "change_24h": change_24h,
        "reasons": reasons,
        "details": {
            "rsi": round(rsi, 1) if rsi else None,
            "macd": {
                "line": round(macd_line_val, 2) if macd_line_val else None,
                "signal": round(macd_signal_val, 2) if macd_signal_val else None,
                "histogram": round(macd_hist_val, 4) if macd_hist_val else None,
            },
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "sma_200": round(sma_200, 2) if sma_200 else None,
            "bollinger": {
                "upper": round(bb_upper_val, 2) if bb_upper_val else None,
                "middle": round(bb_mid_val, 2) if bb_mid_val else None,
                "lower": round(bb_lower_val, 2) if bb_lower_val else None,
            },
            "support_resistance": {
                "support": sr.get("support"),
                "resistance": sr.get("resistance"),
                "upside_pct": upside,
                "downside_pct": downside,
            },
            "fear_greed": fng,
            "global_metrics": global_metrics,
        },        "updated_at": datetime.now(timezone.utc).isoformat(),
}
