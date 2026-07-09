import asyncio
import sys
sys.path.insert(0, '/app')

# First test CoinGecko directly
from app.services.price_service import fetch_btc_chart, fetch_btc_price

async def test_coingecko():
    print("=== Testing CoinGecko ===")
    for days in [30, 90, 365, 1095]:
        chart = await fetch_btc_chart(days)
        if chart:
            print(f"  Chart {days}d: OK ({len(chart)} points)")
        else:
            print(f"  Chart {days}d: FAIL (None)")
    
    price = await fetch_btc_price()
    print(f"  Price: {price}")

asyncio.run(test_coingecko())

# Test DCA simulation
from app.database.database import async_session
from sqlalchemy import select
from app.models.models import User
from app.services.dca_simulator import simulate_dca

async def test_dca():
    print("\n=== Testing DCA ===")
    async with async_session() as db:
        users = await db.execute(select(User.id))
        user_ids = users.scalars().all()
        print(f"Users: {list(user_ids)}")
        
        for uid in user_ids:
            print(f"\n--- User {uid} ---")
            try:
                r = await simulate_dca(uid, db)
                if r is None:
                    print(f"  DCA: NONE (returned None)")
                else:
                    print(f"  DCA: OK")
                    print(f"  Keys: {list(r.keys())}")
            except Exception as e:
                print(f"  DCA: ERROR - {type(e).__name__}: {e}")

asyncio.run(test_dca())
