# =============================================================
# api/alerts.py — Endpoints de alertas
# =============================================================

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.models.models import User, Alert
from app.schemas.schemas import AlertCreate, AlertOut
from app.auth.auth import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("/", response_model=List[AlertOut])
async def list_alerts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Alert)
        .where(Alert.user_id == user.id)
        .order_by(Alert.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=AlertOut, status_code=201)
async def create_alert(
    data: AlertCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    alert = Alert(
        user_id=user.id,
        alert_type=data.alert_type,
        target_value=data.target_value,
        asset=data.asset,
        note=data.note or "",
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")

    await db.delete(alert)
    await db.commit()


@router.put("/{alert_id}/toggle", response_model=AlertOut)
async def toggle_alert(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")

    alert.active = not alert.active
    if alert.active:
        alert.triggered = False
        alert.triggered_at = None

    await db.commit()
    await db.refresh(alert)
    return alert
