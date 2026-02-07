"""
Reminders Worker - Send birthday and anniversary wishes daily.
"""

import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, extract
from app.database import get_db_session
from app.models.user import User
from app.services.gupshup_service import GupshupService

logger = logging.getLogger(__name__)


async def send_birthday_reminders() -> int:
    """Send birthday wishes to users matching today (IST)."""
    ist = ZoneInfo("Asia/Kolkata")
    today = datetime.now(ist)
    month = today.month
    day = today.day
    
    logger.info(f"Checking for birthdays on {day}/{month} (IST)")
    
    count = 0
    gupshup = GupshupService()
    
    async with get_db_session() as db:
        # Query users with matching DOB day/month
        result = await db.execute(
            select(User)
            .where(extract('month', User.dob) == month)
            .where(extract('day', User.dob) == day)
        )
        users = result.scalars().all()
        
        for user in users:
            try:
                # Send generic wish or template
                msg = f"🎂 జన్మదిన శుభాకాంక్షలు {user.name or ''} గారు!\n\nమీ జీవితం ఆయురారోగ్య ఐశ్వర్యాలతో నిండాలని కోరుకుంటున్నాం.\n\n- శుభమస్తు పరివారం 🙏"
                
                await gupshup.send_text_message(
                    phone=user.phone,
                    message=msg
                )
                count += 1
                logger.info(f"Sent birthday wish to {user.phone}")
            except Exception as e:
                logger.error(f"Failed to send birthday wish to {user.phone}: {e}")
                
    return count


async def send_anniversary_reminders() -> int:
    """Send anniversary wishes to users matching today (IST)."""
    ist = ZoneInfo("Asia/Kolkata")
    today = datetime.now(ist)
    month = today.month
    day = today.day
    
    logger.info(f"Checking for anniversaries on {day}/{month} (IST)")
    
    count = 0
    gupshup = GupshupService()
    
    async with get_db_session() as db:
        # Query users with matching Anniversary day/month
        result = await db.execute(
            select(User)
            .where(extract('month', User.wedding_anniversary) == month)
            .where(extract('day', User.wedding_anniversary) == day)
        )
        users = result.scalars().all()
        
        for user in users:
            try:
                msg = f"💍 పెళ్లిరోజు శుభాకాంక్షలు {user.name or ''} గారు!\n\nమీ దాంపత్యం కలకాలం సుఖసంతోషాలతో వర్ధిల్లాలి.\n\n- శుభమస్తు పరివారం 🙏"
                
                await gupshup.send_text_message(
                    phone=user.phone,
                    message=msg
                )
                count += 1
                logger.info(f"Sent anniversary wish to {user.phone}")
            except Exception as e:
                logger.error(f"Failed to send anniversary wish to {user.phone}: {e}")
                
    return count


async def run_reminders_worker():
    """Entry point for daily cron."""
    logger.info("Starting reminders worker...")
    b_count = await send_birthday_reminders()
    a_count = await send_anniversary_reminders()
    logger.info(f"Reminders completed. Birthdays: {b_count}, Anniversaries: {a_count}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_reminders_worker())
