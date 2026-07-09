# =============================================================
# indicator_service.py — Indicadores técnicos
# =============================================================

import logging
import math
from typing import Optional

import numpy as np
import pandas as pd

from app.services.price_service import fetch_btc_chart

logger = logging.getLogger("tokomagraf_api")


def calculate_sma(values: list[float], period: int) -> list[Optional[float]]:
    series = pd.Series(values)
    sma = series.rolling(window=period).mean()
    return [float(v) if not pd.isna(v) else None for v in sma]


def calculate_ema(values: list[float], period: int) -> list[Optional[float]]:
    series = pd.Series(values)
    ema = series.ewm(span=period, adjust=False).mean()
    return [float(v) if not pd.isna(v) else None for v in ema]


def calculate_rsi(values: list[float], period: int = 14) -> list[Optional[float]]:
    series = pd.Series(values)
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.finfo(float).eps)
    rsi = 100 - (100 / (1 + rs))
    return [float(v) if not pd.isna(v) else None for v in rsi]


def calculate_macd(values: list[float]):
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


def calculate_bollinger(values: list[float], period: int = 20, std_dev: float = 2.0):
    series = pd.Series(values)
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return (
        [float(v) if not pd.isna(v) else None for v in upper],
        [float(v) if not pd.isna(v) else None for v in sma],
        [float(v) if not pd.isna(v) else None for v in lower],
    )


def calculate_atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[Optional[float]]:
    if len(highs) < 2:
        return [None] * len(highs)
    tr = []
    for i in range(1, len(closes)):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i-1])
        lc = abs(lows[i] - closes[i-1])
        tr.append(max(hl, hc, lc))
    tr = [0] + tr  # first value
    series = pd.Series(tr)
    atr = series.rolling(window=period).mean()
    return [float(v) if not pd.isna(v) else None for v in atr]


def find_support_resistance(data: list[float]) -> dict:
    """Encuentra niveles de soporte y resistencia."""
    if len(data) < 20:
        return {"support": None, "resistance": None}

    highs, lows = [], []
    for i in range(5, len(data) - 5):
        if all(data[i] >= data[i-j] for j in range(1, 6)) and all(data[i] >= data[i+j] for j in range(1, 6)):
            highs.append(data[i])
        if all(data[i] <= data[i-j] for j in range(1, 6)) and all(data[i] <= data[i+j] for j in range(1, 6)):
            lows.append(data[i])

    if not highs or not lows:
        return {"support": None, "resistance": None}

    def cluster(vals, threshold=0.02):
        if not vals:
            return []
        vals = sorted(vals)
        clusters = [[vals[0]]]
        for v in vals[1:]:
            if abs(v - clusters[-1][-1]) / max(clusters[-1][-1], 0.01) < threshold:
                clusters[-1].append(v)
            else:
                clusters.append([v])
        return [round(sum(c)/len(c), 2) for c in clusters]

    res_levels = cluster(highs)
    sup_levels = cluster(lows)
    current = data[-1]
    above = [r for r in res_levels if r > current]
    below = [s for s in sup_levels if s < current]
    return {
        "support": max(below) if below else (min(sup_levels) if sup_levels else None),
        "resistance": min(above) if above else (max(res_levels) if res_levels else None),
        "all_supports": sup_levels[:3],
        "all_resistances": res_levels[:3],
    }


async def get_full_analysis() -> Optional[dict]:
    """Obtiene análisis técnico completo desde datos de CoinGecko."""
    chart_data = await fetch_btc_chart(90)
    if not chart_data or len(chart_data) < 30:
        return None

    prices = [d["price"] for d in chart_data]
    current_price = prices[-1]

    sma_50_raw = calculate_sma(prices, min(50, len(prices)))
    sma_200_raw = calculate_sma(prices, min(200, len(prices)))
    rsi_raw = calculate_rsi(prices, 14)
    macd_line, macd_signal, macd_hist = calculate_macd(prices)
    bb_upper, bb_mid, bb_lower = calculate_bollinger(prices)

    sma_50 = sma_50_raw[-1] if sma_50_raw and sma_50_raw[-1] is not None else None
    sma_200 = sma_200_raw[-1] if sma_200_raw and sma_200_raw[-1] is not None else None
    rsi = rsi_raw[-1] if rsi_raw and rsi_raw[-1] is not None else None

    # MACD cross
    macd_cross = "none"
    if len(macd_line) >= 2 and len(macd_signal) >= 2:
        pm = macd_line[-2] if macd_line[-2] is not None else 0
        ps = macd_signal[-2] if macd_signal[-2] is not None else 0
        cm = macd_line[-1] if macd_line[-1] is not None else 0
        cs = macd_signal[-1] if macd_signal[-1] is not None else 0
        if pm <= ps and cm > cs:
            macd_cross = "alcista"
        elif pm >= ps and cm < cs:
            macd_cross = "bajista"

    # Tendencia
    trend = "lateral"
    if sma_50 and sma_200:
        if sma_50 > sma_200 * 1.03:
            trend = "alcista"
        elif sma_50 < sma_200 * 0.97:
            trend = "bajista"
    elif sma_50:
        if current_price > sma_50 * 1.05:
            trend = "alcista"
        elif current_price < sma_50 * 0.95:
            trend = "bajista"

    sr = find_support_resistance(prices)

    # Señales
    signals = []
    if rsi is not None:
        if rsi < 30:
            signals.append({"name": "RSI", "signal": "compra", "detail": f"RSI en {rsi:.1f} (sobreventa)", "weight": 3})
        elif rsi < 40:
            signals.append({"name": "RSI", "signal": "compra", "detail": f"RSI en {rsi:.1f} (cerca de sobreventa)", "weight": 1})
        elif rsi > 70:
            signals.append({"name": "RSI", "signal": "venta", "detail": f"RSI en {rsi:.1f} (sobrecompra)", "weight": 3})
        elif rsi > 60:
            signals.append({"name": "RSI", "signal": "venta", "detail": f"RSI en {rsi:.1f} (cerca de sobrecompra)", "weight": 1})

    if sma_50 and sma_200:
        if sma_50 > sma_200:
            signals.append({"name": "SMA", "signal": "compra", "detail": "Golden Cross (SMA 50 > SMA 200)", "weight": 2})
        else:
            signals.append({"name": "SMA", "signal": "venta", "detail": "Death Cross (SMA 50 < SMA 200)", "weight": 2})

    if macd_cross != "none":
        sig_type = "compra" if macd_cross == "alcista" else "venta"
        signals.append({"name": "MACD", "signal": sig_type, "detail": f"Cruce {macd_cross}", "weight": 2})

    buy_weight = sum(s["weight"] for s in signals if s["signal"] == "compra")
    sell_weight = sum(s["weight"] for s in signals if s["signal"] == "venta")

    if buy_weight > sell_weight:
        overall = "compra"
        strength = "alta" if buy_weight >= 5 else "media"
    elif sell_weight > buy_weight:
        overall = "venta"
        strength = "alta" if sell_weight >= 5 else "media"
    else:
        overall = "neutral"
        strength = "baja"

    return {
        "current_price": current_price,
        "trend": trend,
        "overall_signal": overall,
        "signal_strength": strength,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "rsi": round(rsi, 2) if rsi else None,
        "macd": {
            "line": round(macd_line[-1], 2) if macd_line and macd_line[-1] is not None else None,
            "signal": round(macd_signal[-1], 2) if macd_signal and macd_signal[-1] is not None else None,
            "histogram": round(macd_hist[-1], 4) if macd_hist and macd_hist[-1] is not None else None,
            "cross": macd_cross,
        },
        "bollinger": {
            "upper": round(bb_upper[-1], 2) if bb_upper and bb_upper[-1] is not None else None,
            "middle": round(bb_mid[-1], 2) if bb_mid and bb_mid[-1] is not None else None,
            "lower": round(bb_lower[-1], 2) if bb_lower and bb_lower[-1] is not None else None,
        },
        "support_resistance": sr,
        "signals": signals,
    }
