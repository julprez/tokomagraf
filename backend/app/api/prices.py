# =============================================================
# api/prices.py — Endpoints de precios
# =============================================================

from fastapi import APIRouter

from app.services.price_service import fetch_btc_price, fetch_btc_detail, fetch_btc_chart

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.get("/btc")
async def get_btc_price():
    """Precio actual de BTC con cambio 24h."""
    data = await fetch_btc_price()
    if not data:
        return {"error": "No se pudo obtener el precio"}
    return data


@router.get("/btc/detail")
async def get_btc_detail():
    """Detalle completo de BTC (high, low, market_cap, volume)."""
    data = await fetch_btc_detail()
    if not data:
        return {"error": "No se pudo obtener el detalle"}
    return data


@router.get("/btc/chart")
async def get_btc_chart(days: int = 7):
    """Datos históricos para gráfica."""
    if days not in (1, 7, 14, 30, 90):
        days = 7
    data = await fetch_btc_chart(days)
    if not data:
        return {"error": "No se pudieron obtener datos históricos"}
    return {"days": days, "prices": data}
