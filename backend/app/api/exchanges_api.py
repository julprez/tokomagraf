# =============================================================
# api/exchanges_api.py — Endpoints de exchanges (API Keys)
# =============================================================

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.models.models import User, Exchange
from app.schemas.schemas import ExchangeCreate, ExchangeOut
from app.auth.auth import get_current_user

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])


def _mask_key(key: str) -> str:
    """Enmascara una API key mostrando solo primeros y últimos 4 caracteres."""
    if len(key) > 8:
        return key[:4] + "****" + key[-4:]
    return "****"


@router.get("/", response_model=List[ExchangeOut])
async def list_exchanges(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Exchange).where(Exchange.user_id == user.id)
    )
    exchanges = result.scalars().all()
    # Crear copias con API key enmascarada sin modificar los objetos ORM
    masked = []
    for ex in exchanges:
        ex_copy = ExchangeOut(
            id=ex.id,
            name=ex.name,
            api_key=_mask_key(ex.api_key),
            created_at=ex.created_at,
        )
        masked.append(ex_copy)
    return masked


@router.post("/", response_model=ExchangeOut, status_code=201)
async def create_exchange(
    data: ExchangeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(Exchange).where(
            Exchange.user_id == user.id,
            Exchange.name == data.name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Ya existe un exchange con nombre '{data.name}'")

    exchange = Exchange(
        user_id=user.id,
        name=data.name,
        api_key=data.api_key,
        api_secret=data.api_secret,
    )
    db.add(exchange)
    await db.commit()
    await db.refresh(exchange)

    return ExchangeOut(
        id=exchange.id,
        name=exchange.name,
        api_key=_mask_key(exchange.api_key),
        created_at=exchange.created_at,
    )


@router.delete("/{exchange_id}", status_code=204)
async def delete_exchange(
    exchange_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Exchange).where(Exchange.id == exchange_id, Exchange.user_id == user.id)
    )
    exchange = result.scalar_one_or_none()
    if not exchange:
        raise HTTPException(status_code=404, detail="Exchange no encontrado")

    await db.delete(exchange)
    await db.commit()
