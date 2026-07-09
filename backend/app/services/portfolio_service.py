# =============================================================
# portfolio_service.py — Cálculos de cartera
# =============================================================

import logging
from collections import defaultdict
from datetime import date, timedelta, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Operation, Portfolio, DailyHistory
from app.services.price_service import fetch_btc_price

logger = logging.getLogger("tokomagraf_api")


async def get_portfolio(user_id: int, db: AsyncSession) -> Optional[Portfolio]:
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def calculate_balances(user_id: int, db: AsyncSession) -> dict:
    """Calcula balances actuales desde las operaciones."""
    result = await db.execute(
        select(Operation).where(Operation.user_id == user_id)
    )
    ops = result.scalars().all()

    btc = 0.0
    usdc = 0.0
    eur = 0.0
    total_invested = 0.0
    total_btc_cost = 0.0
    total_btc_amount = 0.0

    for op in ops:
        if op.tipo == "buy":
            if op.activo == "BTC":
                btc += op.cantidad
                total_btc_cost += op.cantidad * op.precio + op.comision
                total_btc_amount += op.cantidad
                total_invested += op.cantidad * op.precio + op.comision
            elif op.activo == "USDC":
                usdc += op.cantidad
                total_invested += op.cantidad * op.precio + op.comision
            elif op.activo == "EUR":
                eur += op.cantidad
                total_invested += op.cantidad * op.precio + op.comision

        elif op.tipo == "sell":
            if op.activo == "BTC":
                btc -= op.cantidad
                # Los ingresos de la venta van a USDC
                usdc += op.cantidad * op.precio - op.comision
            elif op.activo == "USDC":
                usdc -= op.cantidad
            elif op.activo == "EUR":
                eur -= op.cantidad

        elif op.tipo == "deposit":
            if op.activo == "BTC":
                btc += op.cantidad
                total_btc_cost += op.cantidad * op.precio
                total_btc_amount += op.cantidad
                total_invested += op.cantidad * op.precio
            elif op.activo == "USDC":
                usdc += op.cantidad
                total_invested += op.cantidad
            elif op.activo == "EUR":
                eur += op.cantidad
                total_invested += op.cantidad

        elif op.tipo == "withdraw":
            if op.activo == "USDC":
                usdc -= op.cantidad
            elif op.activo == "EUR":
                eur -= op.cantidad

    avg_price = (total_btc_cost / total_btc_amount) if total_btc_amount > 0 else None

    return {
        "btc": round(btc, 8),
        "usdc": round(usdc, 2),
        "eur": round(eur, 2),
        "total_invested": round(total_invested, 2),
        "avg_btc_price": round(avg_price, 2) if avg_price else None,
        "trade_count": len(ops),
    }


async def get_dashboard(user_id: int, db: AsyncSession) -> Optional[dict]:
    """Calcula datos completos del dashboard."""
    balances = await calculate_balances(user_id, db)
    price_data = await fetch_btc_price()
    if not price_data:
        return None

    btc_price = price_data["price_usd"]
    btc_value = balances["btc"] * btc_price
    portfolio_value = round(btc_value + balances["usdc"] + balances["eur"], 2)
    total_invested = balances["total_invested"]

    total_pnl = round(portfolio_value - total_invested, 2)
    total_pnl_pct = round((total_pnl / total_invested * 100), 2) if total_invested > 0 else 0.0

    # Guardar snapshot diario (captura el valor de "apertura" del día)
    await save_daily_snapshot(user_id, portfolio_value, balances, btc_price, db)

    # Beneficio diario: comparar con el snapshot de HOY (intradía)
    daily_profit = await get_daily_profit(user_id, portfolio_value, db)
    monthly_profit = await get_monthly_profit(user_id, portfolio_value, db)

    # Primera operación
    first_op = await db.execute(
        select(Operation).where(Operation.user_id == user_id).order_by(Operation.fecha.asc()).limit(1)
    )
    first_trade = first_op.scalar_one_or_none()
    first_trade_date = first_trade.fecha.isoformat()[:10] if first_trade else None

    # Rentabilidad anualizada
    annualized = None
    if first_trade_date and total_invested > 0 and total_pnl != 0:
        days_elapsed = (datetime.utcnow() - first_trade.fecha).days
        if days_elapsed > 0:
            total_return = total_pnl / total_invested
            annualized = round(((1 + total_return) ** (365 / days_elapsed) - 1) * 100, 2)

    return {
        "btc_balance": balances["btc"],
        "usdc_balance": balances["usdc"],
        "btc_price": btc_price,
        "btc_change_24h": price_data.get("change_24h"),
        "portfolio_value": portfolio_value,
        "total_invested": total_invested,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "avg_btc_price": balances["avg_btc_price"],
        "daily_profit": daily_profit,
        "monthly_profit": monthly_profit,
        "annualized_return": annualized,
        "trade_count": balances["trade_count"],
        "first_trade_date": first_trade_date,
        "updated_at": datetime.utcnow().isoformat(),
    }


async def get_daily_profit(user_id: int, current_value: float, db: AsyncSession) -> Optional[float]:
    """
    Resultado del día: compara el valor actual contra el snapshot de HOY
    (primer valor registrado del día = "apertura").
    Si no existe snapshot hoy (primer día), usa el último disponible.
    """
    today = date.today()

    # 1. Intentar snapshot de hoy (comparación intradía)
    result = await db.execute(
        select(DailyHistory).where(
            DailyHistory.user_id == user_id,
            DailyHistory.fecha == today,
        )
    )
    snap = result.scalar_one_or_none()

    # 2. Si no hay snapshot hoy (primer acceso del primer día), usar el más reciente
    if not snap:
        result = await db.execute(
            select(DailyHistory).where(DailyHistory.user_id == user_id)
            .order_by(DailyHistory.fecha.desc()).limit(1)
        )
        snap = result.scalar_one_or_none()

    if not snap:
        return None

    return round(current_value - snap.valor_portfolio, 2)


async def get_monthly_profit(user_id: int, current_value: float, db: AsyncSession) -> Optional[float]:
    target = date.today() - timedelta(days=30)
    result = await db.execute(
        select(DailyHistory).where(
            DailyHistory.user_id == user_id,
            DailyHistory.fecha <= target,
        ).order_by(DailyHistory.fecha.desc()).limit(1)
    )
    snap = result.scalar_one_or_none()
    if not snap:
        return None
    return round(current_value - snap.valor_portfolio, 2)


async def get_chart_data(user_id: int, db: AsyncSession) -> dict:
    """
    Genera todos los datasets para los gráficos de la página de Historial.
    """
    # ── Obtener historial diario ──
    result = await db.execute(
        select(DailyHistory)
        .where(DailyHistory.user_id == user_id)
        .order_by(DailyHistory.fecha.asc())
    )
    daily_history = result.scalars().all()

    # ── Obtener todas las operaciones ordenadas ──
    ops_result = await db.execute(
        select(Operation)
        .where(Operation.user_id == user_id)
        .order_by(Operation.fecha.asc())
    )
    all_ops = ops_result.scalars().all()

    # ── 1. Evolución patrimonio ──
    patrimonio = [
        {
            "fecha": h.fecha.isoformat(),
            "valor": round(h.valor_portfolio, 2),
            "btc": round(h.btc, 8),
            "usdc": round(h.usdc, 2),
        }
        for h in daily_history
    ]

    # ── 2. Ganancia diaria ──
    ganancia_diaria = [
        {
            "fecha": h.fecha.isoformat(),
            "ganancia": round(h.ganancia_dia, 2),
        }
        for h in daily_history
    ]

    # ── 3. Aportes de capital ──
    aportes = []
    running_capital = 0.0
    for op in all_ops:
        if op.tipo == "deposit":
            running_capital += op.cantidad
            aportes.append({
                "fecha": op.fecha.isoformat()[:10] if op.fecha else "",
                "monto": op.cantidad,
                "activo": op.activo,
                "acumulado": round(running_capital, 2),
            })

    # ── 5. Evolución coste medio BTC ──
    coste_medio = []
    btc_total = 0.0
    btc_costo_total = 0.0
    for op in all_ops:
        if op.tipo == "buy" and op.activo == "BTC":
            btc_total += op.cantidad
            btc_costo_total += op.cantidad * op.precio + op.comision
            avg = btc_costo_total / btc_total if btc_total > 0 else 0
            coste_medio.append({
                "fecha": op.fecha.isoformat()[:10] if op.fecha else "",
                "coste_medio": round(avg, 2),
                "btc_acumulado": round(btc_total, 8),
            })
        elif op.tipo == "sell" and op.activo == "BTC":
            # Al vender, el coste medio no cambia, pero baja la cantidad
            btc_total -= op.cantidad
            if btc_total < 0:
                btc_total = 0.0
            coste_medio.append({
                "fecha": op.fecha.isoformat()[:10] if op.fecha else "",
                "coste_medio": round(btc_costo_total / btc_total, 2) if btc_total > 0 else 0,
                "btc_acumulado": round(btc_total, 8),
            })

    # ── 6. Rentabilidad mensual ──
    meses_ordenados = sorted(set(h.fecha.isoformat()[:7] for h in daily_history))
    rentabilidad_mensual = []
    for mes in meses_ordenados:
        registros_mes = [h for h in daily_history if h.fecha.isoformat()[:7] == mes]
        if not registros_mes:
            continue
        inicio_mes = registros_mes[0].valor_portfolio
        fin_mes = registros_mes[-1].valor_portfolio
        aportes_mes = sum(
            op.cantidad for op in all_ops
            if op.tipo == "deposit" and op.fecha and op.fecha.isoformat()[:7] == mes
        )
        base_ajustada = inicio_mes + aportes_mes
        ret_mensual = round((fin_mes - base_ajustada) / base_ajustada * 100, 2) if base_ajustada > 0 else 0.0
        rentabilidad_mensual.append({
            "mes": mes,
            "retorno": ret_mensual,
            "inicio": round(inicio_mes, 2),
            "fin": round(fin_mes, 2),
            "aportes": round(aportes_mes, 2),
        })

    # ── 7. Beneficio acumulado ──
    # Calculamos inversión total acumulada día a día
    beneficio_acumulado = []
    for h in daily_history:
        total_inv = 0.0
        for op in all_ops:
            if op.fecha and op.fecha.date() <= h.fecha:
                if op.tipo == "buy":
                    total_inv += op.cantidad * op.precio + op.comision
                elif op.tipo == "deposit":
                    total_inv += op.cantidad
        pnl = round(h.valor_portfolio - total_inv, 2)
        beneficio_acumulado.append({
            "fecha": h.fecha.isoformat(),
            "pnl": pnl,
            "invertido": round(total_inv, 2),
        })

    return {
        "patrimonio": patrimonio,
        "ganancia_diaria": ganancia_diaria,
        "beneficio_acumulado": beneficio_acumulado,
        "aportes": aportes,
        "coste_medio": coste_medio,
        "rentabilidad_mensual": rentabilidad_mensual,
    }


async def save_daily_snapshot(user_id: int, value: float, balances: dict, btc_price: float, db: AsyncSession):
    today = date.today()
    result = await db.execute(
        select(DailyHistory).where(
            DailyHistory.user_id == user_id,
            DailyHistory.fecha == today,
        )
    )
    if result.scalar_one_or_none():
        return  # Ya existe snapshot hoy

    # Calcular ganancia del día
    yesterday = today - timedelta(days=1)
    prev = await db.execute(
        select(DailyHistory).where(
            DailyHistory.user_id == user_id,
            DailyHistory.fecha == yesterday,
        )
    )
    prev_snap = prev.scalar_one_or_none()
    ganancia = round(value - prev_snap.valor_portfolio, 2) if prev_snap else 0.0

    snap = DailyHistory(
        user_id=user_id,
        fecha=today,
        valor_portfolio=value,
        ganancia_dia=ganancia,
        btc=balances["btc"],
        usdc=balances["usdc"],
    )
    db.add(snap)
    await db.commit()
