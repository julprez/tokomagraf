# =============================================================
# api/portfolio_api.py — Endpoints de cartera y analítica
# =============================================================

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.models.models import User, DailyHistory
from app.schemas.schemas import DashboardData, DailyHistoryOut
from app.auth.auth import get_current_user
from app.services.portfolio_service import get_dashboard, calculate_balances, get_chart_data
from app.services.indicator_service import get_full_analysis

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("/dashboard")
async def dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Panel principal de la cartera."""
    data = await get_dashboard(user.id, db)
    if not data:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="No se pudo obtener el dashboard")
    return data


@router.get("/balances")
async def balances(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Balances actuales."""
    return await calculate_balances(user.id, db)


@router.get("/history", response_model=List[DailyHistoryOut])
async def portfolio_history(
    limit: int = 30,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Historial diario de la cartera."""
    result = await db.execute(
        select(DailyHistory)
        .where(DailyHistory.user_id == user.id)
        .order_by(DailyHistory.fecha.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/charts")
async def portfolio_charts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Datasets completos para gráficos del historial."""
    data = await get_chart_data(user.id, db)
    return data


@router.get("/analysis")
async def analysis():
    """Análisis técnico completo de BTC."""
    data = await get_full_analysis()
    if not data:
        return {"error": "No hay suficientes datos para el análisis"}
    return data


@router.get("/summary")
async def summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resumen ejecutivo de la cartera."""
    dash = await get_dashboard(user.id, db)
    if not dash:
        return {"error": "No se pudo obtener el resumen"}
    return {
        "patrimonio_total": dash["portfolio_value"],
        "invertido": dash["total_invested"],
        "pnl": dash["total_pnl"],
        "pnl_pct": dash["total_pnl_pct"],
        "btc": dash["btc_balance"],
        "btc_precio": dash["btc_price"],
        "usdc": dash["usdc_balance"],
        "trades": dash["trade_count"],
    }
