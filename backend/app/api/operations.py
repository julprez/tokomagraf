# =============================================================
# api/operations.py — Endpoints de operaciones
# =============================================================

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
import io
import csv

from app.database.database import get_db
from app.models.models import User, Operation, Portfolio
from app.schemas.schemas import OperationCreate, OperationOut
from app.auth.auth import get_current_user
from app.services.portfolio_service import calculate_balances
from app.services.dca_simulator import invalidate_dca_cache

router = APIRouter(prefix="/api/operations", tags=["operations"])


@router.get("/", response_model=List[OperationOut])
async def list_operations(
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Operation)
        .where(Operation.user_id == user.id)
        .order_by(Operation.fecha.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/buy", response_model=OperationOut, status_code=201)
async def buy(
    data: OperationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.tipo != "buy":
        raise HTTPException(status_code=400, detail="Usá /api/operations/buy para compras")

    op = Operation(
        user_id=user.id,
        tipo="buy",
        activo=data.activo,
        cantidad=data.cantidad,
        precio=data.precio,
        comision=data.comision,
        notes=data.notes or "",
    )
    if data.fecha:
        op.fecha = data.fecha

    db.add(op)
    await db.commit()
    await db.refresh(op)
    invalidate_dca_cache(user.id)
    return op


@router.post("/sell", response_model=OperationOut, status_code=201)
async def sell(
    data: OperationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.tipo != "sell":
        raise HTTPException(status_code=400, detail="Usá /api/operations/sell para ventas")

    # Verificar balance suficiente
    balances = await calculate_balances(user.id, db)

    if data.activo == "BTC" and balances["btc"] < data.cantidad:
        raise HTTPException(status_code=400, detail=f"BTC insuficiente. Tenés {balances['btc']:.8f}")
    if data.activo == "USDC" and balances["usdc"] < data.cantidad:
        raise HTTPException(status_code=400, detail=f"USDC insuficiente. Tenés {balances['usdc']:.2f}")

    op = Operation(
        user_id=user.id,
        tipo="sell",
        activo=data.activo,
        cantidad=data.cantidad,
        precio=data.precio,
        comision=data.comision,
        notes=data.notes or "",
    )
    if data.fecha:
        op.fecha = data.fecha

    db.add(op)
    await db.commit()
    await db.refresh(op)
    invalidate_dca_cache(user.id)
    return op


@router.post("/deposit", response_model=OperationOut, status_code=201)
async def deposit(
    data: OperationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.tipo != "deposit":
        raise HTTPException(status_code=400, detail="Usá /api/operations/deposit para depósitos")

    op = Operation(
        user_id=user.id,
        tipo="deposit",
        activo=data.activo,
        cantidad=data.cantidad,
        precio=data.precio,
        comision=data.comision,
        notes=data.notes or "",
    )
    if data.fecha:
        op.fecha = data.fecha

    db.add(op)
    await db.commit()
    await db.refresh(op)
    invalidate_dca_cache(user.id)
    return op


@router.post("/withdraw", response_model=OperationOut, status_code=201)
async def withdraw(
    data: OperationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.tipo != "withdraw":
        raise HTTPException(status_code=400, detail="Usá /api/operations/withdraw para retiradas")

    balances = await calculate_balances(user.id, db)
    if data.activo == "USDC" and balances["usdc"] < data.cantidad:
        raise HTTPException(status_code=400, detail=f"USDC insuficiente. Tenés {balances['usdc']:.2f}")

    op = Operation(
        user_id=user.id,
        tipo="withdraw",
        activo=data.activo,
        cantidad=data.cantidad,
        precio=data.precio,
        comision=data.comision,
        notes=data.notes or "",
    )
    if data.fecha:
        op.fecha = data.fecha

    db.add(op)
    await db.commit()
    await db.refresh(op)
    invalidate_dca_cache(user.id)
    return op


@router.get("/history", response_model=List[OperationOut])
async def get_history(
    days: int = 30,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Obtiene historial de los últimos N días."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Operation)
        .where(Operation.user_id == user.id, Operation.fecha >= since)
        .order_by(Operation.fecha.desc())
    )
    return result.scalars().all()


@router.get("/export")
async def export_csv(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Exporta todas las operaciones a CSV."""
    result = await db.execute(
        select(Operation)
        .where(Operation.user_id == user.id)
        .order_by(Operation.fecha.asc())
    )
    ops = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Tipo", "Activo", "Cantidad", "Precio USD", "Comision USD", "Notas", "Fecha"])
    for op in ops:
        writer.writerow([
            op.id,
            op.tipo,
            op.activo,
            op.cantidad,
            f"{op.precio:.2f}" if op.precio else "0.00",
            f"{op.comision:.2f}" if op.comision else "0.00",
            op.notes or "",
            op.fecha.isoformat() if op.fecha else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tokomagraf_operaciones.csv"},
    )
