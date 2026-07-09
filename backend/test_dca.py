import asyncio
import sys
sys.path.insert(0, '/app')

from app.database.database import SessionLocal
from app.services.dca_simulator import simulate_dca
from sqlalchemy import select

async def test():
    async with SessionLocal() as db:
        # Check operations
        from app.models.models import Operation, DcaStrategy
        
        ops_result = await db.execute(
            select(Operation).order_by(Operation.fecha.asc())
        )
        ops = ops_result.scalars().all()
        print(f"Total operations: {len(ops)}")
        for op in ops[:5]:
            print(f"  - tipo={op.tipo} activo={op.activo} cantidad={op.cantidad} precio={op.precio} fecha={op.fecha} user_id={op.user_id}")
        
        # Try DCA for each user
        users_result = await db.execute(select(User.id))
        user_ids = users_result.scalars().all()
        print(f"\nUsers: {list(user_ids)}")
        
        for uid in user_ids:
            print(f"\n--- Testing DCA for user {uid} ---")
            try:
                r = await simulate_dca(uid, db)
                if r is None:
                    print(f"DCA for user {uid}: NONE")
                else:
                    print(f"DCA for user {uid}: OK - keys={list(r.keys())}")
                    if 'real' in r:
                        print(f"  Real BTC: {r['real'].get('btc_acumulado')}")
            except Exception as e:
                print(f"DCA for user {uid}: ERROR - {e}")
                import traceback
                traceback.print_exc()

asyncio.run(test())
