import asyncio
import sys, logging
sys.path.insert(0, '/app')

logging.basicConfig(level=logging.DEBUG)

from app.database.database import async_session
from sqlalchemy import select
from app.models.models import User, Operation, DcaStrategy
from datetime import date

async def debug_dca():
    async with async_session() as db:
        users = await db.execute(select(User.id))
        user_ids = users.scalars().all()
        print(f"Users: {list(user_ids)}")
        
        for uid in user_ids:
            print(f"\n{'='*60}")
            print(f"DEBUGGING USER {uid}")
            print(f"{'='*60}")
            
            # Check strategy
            strat = await db.execute(
                select(DcaStrategy).where(DcaStrategy.user_id == uid)
            )
            s = strat.scalar_one_or_none()
            print(f"Strategy: freq={s.frequency if s else 'N/A'}, day={s.day if s else 'N/A'}")
            
            # Check operations
            ops = await db.execute(
                select(Operation).where(Operation.user_id == uid).order_by(Operation.fecha.asc())
            )
            all_ops = ops.scalars().all()
            print(f"Operations: {len(all_ops)}")
            
            if not all_ops:
                print("=> FAIL: no operations")
                continue
            
            # Check total capital
            total_capital = 0.0
            for op in all_ops:
                if op.tipo == "buy":
                    total_capital += op.cantidad * op.precio + op.comision
                elif op.tipo == "deposit":
                    total_capital += op.cantidad
            print(f"Total capital: {total_capital}")
            
            # Check start/end dates
            first_op = all_ops[0]
            start_date = first_op.fecha.date() if hasattr(first_op.fecha, 'date') else first_op.fecha
            today = date.today()
            days_span = (today - start_date).days + 30
            days_span = max(30, min(365, days_span))
            print(f"First op: {first_op.fecha}, Start: {start_date}, Today: {today}, Days: {days_span}")
            
            # Try to get chart
            from app.services.price_service import fetch_btc_chart
            btc_chart = None
            for try_days in [days_span, 365, 90, 30]:
                chart = await fetch_btc_chart(try_days)
                if chart and len(chart) >= 2:
                    btc_chart = chart
                    print(f"Chart: OK with {try_days}d ({len(chart)} points)")
                    break
                print(f"Chart: FAIL with {try_days}d")
            
            if not btc_chart or len(btc_chart) < 2:
                print("=> FAIL: no chart data")
                continue
            
            # Build price map
            from datetime import datetime
            price_map = {}
            for entry in btc_chart:
                ts_ms = entry.get("timestamp", 0)
                dt = datetime.fromtimestamp(ts_ms / 1000)
                key = dt.date().isoformat()
                if key not in price_map:
                    price_map[key] = entry["price"]
            print(f"Price map: {len(price_map)} dates, range: {min(price_map.keys())} to {max(price_map.keys())}")
            
            # Try generating DCA schedule
            from app.services.dca_simulator import _generate_dca_schedule
            try:
                purchases = _generate_dca_schedule(start_date, today, total_capital, s, price_map)
                print(f"DCA purchases: {len(purchases)}")
                if purchases:
                    print(f"  First: {purchases[0]['fecha']} ({purchases[0]['amount']} @ {purchases[0]['precio']})")
                    print(f"  Last:  {purchases[-1]['fecha']} ({purchases[-1]['amount']} @ {purchases[-1]['precio']})")
                else:
                    print("=> FAIL: no DCA purchases generated")
                    # Show why
                    print("  Checking if dates are in price_map...")
                    from datetime import timedelta
                    current = start_date
                    count = 0
                    while current <= today:
                        if current.isoformat() in price_map:
                            count += 1
                        current += timedelta(days=1)
                    print(f"  {count} dates from {start_date} to {today} have prices")
            except Exception as e:
                print(f"  _generate_dca_schedule ERROR: {e}")
                import traceback
                traceback.print_exc()

asyncio.run(debug_dca())
