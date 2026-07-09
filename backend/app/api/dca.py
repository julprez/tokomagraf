# =============================================================
# api/dca.py — Endpoints de DCA (Dollar-Cost Averaging)
# =============================================================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.models.models import User, DcaStrategy
from app.schemas.schemas import DcaConfigUpdate
from app.auth.auth import get_current_user
from app.services.dca_simulator import simulate_dca, invalidate_dca_cache

router = APIRouter(prefix="/api/dca", tags=["dca"])


@router.get("/comparison")
async def get_dca_comparison(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compara la cartera real del usuario con una simulación DCA."""
    data = await simulate_dca(user.id, db)
    if not data:
        raise HTTPException(status_code=400, detail="No hay suficientes datos para simular DCA")
    return data


@router.get("/config")
async def get_dca_config(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Obtiene la configuración actual de la estrategia DCA."""
    result = await db.execute(
        select(DcaStrategy).where(DcaStrategy.user_id == user.id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        # Crear configuración por defecto
        strategy = DcaStrategy(user_id=user.id)
        db.add(strategy)
        await db.commit()
        await db.refresh(strategy)
    return {
        "frequency": strategy.frequency,
        "day": strategy.day,
        "active": strategy.active,
    }


@router.put("/config")
async def update_dca_config(
    data: DcaConfigUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza la configuración de la estrategia DCA."""
    result = await db.execute(
        select(DcaStrategy).where(DcaStrategy.user_id == user.id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        strategy = DcaStrategy(user_id=user.id)
        db.add(strategy)

    if data.frequency is not None:
        strategy.frequency = data.frequency
    if data.day is not None:
        strategy.day = data.day
    if data.active is not None:
        strategy.active = data.active

    await db.commit()
    await db.refresh(strategy)
    invalidate_dca_cache(user.id)
    return {
        "frequency": strategy.frequency,
        "day": strategy.day,
        "active": strategy.active,
    }
