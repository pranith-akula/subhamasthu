import asyncio
from datetime import datetime
from sqlalchemy import select, desc
from app.database import async_session_maker
from app.models.user import User

async def check_recent_engagement():
    print("Checking for recent user engagement in DB...")
    if not async_session_maker:
        print("Database not configured.")
        return

    async with async_session_maker() as db:
        query = select(User).order_by(desc(User.last_engagement_at)).limit(5)
        result = await db.execute(query)
        users = result.scalars().all()
        
        if not users:
            print("No users found with engagement records.")
            return
            
        for user in users:
            try:
                print(f"Phone: {user.phone}, Name: {user.name}, Last Engagement: {user.last_engagement_at}, Streak: {user.streak_days}")
            except UnicodeEncodeError:
                # Fallback for Windows terminal
                safe_name = user.name.encode('ascii', 'replace').decode('ascii')
                print(f"Phone: {user.phone}, Name: {safe_name}, Last Engagement: {user.last_engagement_at}, Streak: {user.streak_days}")

if __name__ == "__main__":
    asyncio.run(check_recent_engagement())
