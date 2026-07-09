# =============================================================
# api/predictions.py — Endpoint de predicción/puntuación
# =============================================================

from fastapi import APIRouter, Depends

from app.auth.auth import get_current_user
from app.models.models import User
from app.services.prediction_service import compute_prediction

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.get("/")
async def get_prediction(user: User = Depends(get_current_user)):
    """Analiza el mercado y devuelve una puntuación de compra/venta (0-100)."""
    data = await compute_prediction()
    if not data:
        return {"error": "No hay suficientes datos para el análisis predictivo"}
    return data
