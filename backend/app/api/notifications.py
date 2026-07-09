# =============================================================
# api/notifications.py — Endpoints de notificaciones
# =============================================================

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select, update, func

from app.database.database import get_db
from app.models.models import User, Notification
from app.schemas.schemas import NotificationOut
from app.auth.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/", response_model=List[NotificationOut])
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        query = query.where(Notification.read == False)  # noqa: E712

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/unread-count")
async def unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == user.id, Notification.read == False)  # noqa: E712
    )
    count = result.scalar() or 0
    return {"count": count}


@router.put("/{notification_id}/read", response_model=NotificationOut)
async def mark_as_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")

    notif.read = True
    await db.commit()
    await db.refresh(notif)
    return notif


@router.put("/read-all")
async def mark_all_as_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read == False)  # noqa: E712
        .values(read=True)
    )
    await db.commit()
    return {"status": "ok"}
