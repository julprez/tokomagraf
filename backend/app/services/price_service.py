# =============================================================
# price_service.py — Servicio de precios desde CoinGecko
# =============================================================

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import aiohttp

logger = logging.getLogger("tokomagraf_api")

COINGECKO_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
COINGECKO_MARKET_URL = "https://api.coingecko.com/api/v3/coins/bitcoin?localization=false&tickers=false&community_data=false&developer_data=false&sparkline=false"
COINGECKO_CHART_URL = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days={days}"
COINGECKO_GLOBAL_URL = "https://api.coingecko.com/api/v3/global"
FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1&date_format=global"
COINGECKO_DOMINANCE_URL = "https://api.coingecko.com/api/v3/global"

# ── Caché en memoria ──
_cache: dict[str, tuple[float, object]] = {}

_CACHE_TTL = {
    "price": 30,         # 30s para precio
    "chart": 120,        # 2 min para charts (los históricos no cambian tan rápido)
    "detail": 60,        # 1 min para detalle
    "global": 120,       # 2 min para métricas globales
    "fear_greed": 300,   # 5 min para fear & greed
}


def _cache_get(key: str) -> object:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.monotonic() - ts > _CACHE_TTL.get(key.split(":")[0], 60):
        del _cache[key]
        return None
    return value


def _cache_set(key: str, value: object) -> None:
    _cache[key] = (time.monotonic(), value)


async def fetch_fear_greed() -> Optional[dict]:
    """Índice de Miedo y Codicia (0-100)."""
    cached = _cache_get("fear_greed")
    if cached:
        return cached
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FEAR_GREED_URL, timeout=10) as resp:
                if resp.status != 200:
                    logger.warning("alternative.me respondió %s", resp.status)
                    return None
                data = await resp.json()
                items = data.get("data", [])
                if not items:
                    return None
                item = items[0]
                result = {
                    "value": int(item.get("value", 50)),
                    "classification": item.get("value_classification", "Neutral"),
                    "updated_at": item.get("timestamp"),
                }
                _cache_set("fear_greed", result)
                return result
    except Exception as e:
        logger.error("Error obteniendo Fear & Greed: %s", e)
        return None


async def fetch_btc_dominance() -> Optional[float]:
    """Dominancia de BTC como porcentaje del market cap total cripto."""
    cached = _cache_get("global:dominance")
    if cached:
        return cached
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(COINGECKO_GLOBAL_URL, timeout=10) as resp:
                if resp.status != 200:
                    logger.warning("CoinGecko global respondió %s", resp.status)
                    return None
                data = await resp.json()
                dom = data.get("data", {}).get("market_cap_percentage", {}).get("btc")
                result = round(float(dom), 2) if dom is not None else None
                if result is not None:
                    _cache_set("global:dominance", result)
                return result
    except Exception as e:
        logger.error("Error obteniendo dominancia BTC: %s", e)
        return None


async def fetch_global_metrics() -> Optional[dict]:
    """Métricas globales del mercado cripto (dominancia, market cap total, volumen)."""
    cached = _cache_get("global:metrics")
    if cached:
        return cached
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(COINGECKO_GLOBAL_URL, timeout=10) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                d = data.get("data", {})
                result = {
                    "btc_dominance": round(float(d.get("market_cap_percentage", {}).get("btc", 0)), 2),
                    "total_market_cap": round(float(d.get("total_market_cap", {}).get("usd", 0)), 2),
                    "total_volume": round(float(d.get("total_volume", {}).get("usd", 0)), 2),
                }
                _cache_set("global:metrics", result)
                return result
    except Exception as e:
        logger.error("Error obteniendo métricas globales: %s", e)
        return None


async def fetch_btc_price() -> Optional[dict]:
    cached = _cache_get("price")
    if cached:
        return cached
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(COINGECKO_PRICE_URL, timeout=10) as resp:
                if resp.status != 200:
                    logger.warning("CoinGecko respondió %s", resp.status)
                    return None
                data = await resp.json()
                btc = data.get("bitcoin", {})
                price = btc.get("usd")
                change = btc.get("usd_24h_change")
                if price is None:
                    return None
                result = {
                    "price_usd": round(float(price), 2),
                    "change_24h": round(float(change), 2) if change is not None else None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                _cache_set("price", result)
                return result
    except Exception as e:
        logger.error("Error obteniendo precio BTC: %s", e)
        return None


async def fetch_btc_detail() -> Optional[dict]:
    cached = _cache_get("detail")
    if cached:
        return cached
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(COINGECKO_MARKET_URL, timeout=10) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                md = data.get("market_data", {})
                result = {
                    "price_usd": round(float(md.get("current_price", {}).get("usd", 0)), 2),
                    "change_24h": round(float(md.get("price_change_percentage_24h", 0)), 2) if md.get("price_change_percentage_24h") else None,
                    "high_24h": round(float(md.get("high_24h", {}).get("usd", 0)), 2) if md.get("high_24h") else None,
                    "low_24h": round(float(md.get("low_24h", {}).get("usd", 0)), 2) if md.get("low_24h") else None,
                    "market_cap": round(float(md.get("market_cap", {}).get("usd", 0)), 2) if md.get("market_cap") else None,
                    "volume": round(float(md.get("total_volume", {}).get("usd", 0)), 2) if md.get("total_volume") else None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                _cache_set("detail", result)
                return result
    except Exception as e:
        logger.error("Error obteniendo detalle BTC: %s", e)
        return None


async def fetch_btc_chart(days: int = 7) -> Optional[list[dict]]:
    cache_key = f"chart:{days}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    url = COINGECKO_CHART_URL.format(days=days)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                prices = data.get("prices", [])
                result = [
                    {"timestamp": int(ts), "price": round(float(p), 2)}
                    for ts, p in prices
                ]
                _cache_set(cache_key, result)
                return result
    except Exception as e:
        logger.error("Error obteniendo chart BTC: %s", e)
        return None
