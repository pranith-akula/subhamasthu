
import asyncio
import logging
import random
import sys
import os
sys.path.append(os.getcwd())
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from app.database import get_db_context
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_trust_engine():
    """
    Initialize Trust Engine fields for all users.
    - Set nurture_track (Random A/B/C)
    - Set surprise_day (Random 14-20)
    - Set next_rashi_at (Tomorrow 7 AM Local)
    - Set next_nurture_at (Tomorrow 9 PM Local)
    """
    async with get_db_context() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        logger.info(f"Found {len(users)} users to initialize")
        
        tracks = ["DEVOTION", "SECURITY", "GROWTH"]
        
        for user in users:
            # 1. Set Track
            if not user.nurture_track:
                user.nurture_track = random.choice(tracks)
                
            # 2. Set Surprise Day
            if user.surprise_day == 17 or user.surprise_day == 0: # Default was 17
                user.surprise_day = random.randint(14, 20)
                
            # 3. Calculate Timestamps
            # Get User TZ
            try:
                tz = ZoneInfo(user.tz)
            except:
                tz = ZoneInfo("America/Chicago")
                
            now_local = datetime.now(tz)
            tomorrow_local = now_local + timedelta(days=1)
            
            # Next Rashi: Tomorrow 7 AM
            next_rashi_local = tomorrow_local.replace(hour=7, minute=0, second=0, microsecond=0)
            
            # Next Nurture: Tomorrow 9 PM
            next_nurture_local = tomorrow_local.replace(hour=21, minute=0, second=0, microsecond=0)
            
            # Convert to UTC
            user.next_rashi_at = next_rashi_local.astimezone(ZoneInfo("UTC"))
            user.next_nurture_at = next_nurture_local.astimezone(ZoneInfo("UTC"))
            
            # Reset Nurture Day if 0
            if user.nurture_day == 0:
                 user.nurture_day = 1
                 
            logger.info(f"Initialized {user.phone}: Track={user.nurture_track}, Rashi={user.next_rashi_at}, Nurture={user.next_nurture_at}")
            
        await db.commit()
        logger.info("Initialization Complete")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(init_trust_engine())
