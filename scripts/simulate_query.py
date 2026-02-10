import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from app.database import async_session_maker
from app.models.user import User

async def simulate_dashboard_query():
    print("Simulating Dashboard Queries...")
    async with async_session_maker() as db:
        now = datetime.now(timezone.utc)
        print(f"Current UTC now: {now}")
        
        # Query 1: Active 24h
        active_24h_query = select(func.count(User.id)).where(User.last_engagement_at >= now - timedelta(hours=24))
        active_24h = (await db.execute(active_24h_query)).scalar() or 0
        print(f"Active 24h Count: {active_24h}")
        
        # Query 2: All users with last_engagement_at
        engagement_check = select(User.phone, User.last_engagement_at).where(User.last_engagement_at.isnot(None))
        res = await db.execute(engagement_check)
        for row in res.all():
            phone, eng = row
            diff = now - eng
            is_valid = eng >= now - timedelta(hours=24)
            print(f"Phone: {phone}, Last Engagement: {eng}, Diff: {diff}, >= 24h: {is_valid}")

if __name__ == "__main__":
    asyncio.run(simulate_dashboard_query())
