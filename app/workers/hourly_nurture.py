
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.workers.celery_app import celery_app
from app.database import get_db_context
from app.models.user import User
from app.services.nurture_service import NurtureService
from app.services.rashiphalalu_service import RashiphalaluService

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def process_hourly_nurture(self):
    """
    Celery task to run the hourly nurture check.
    """
    try:
        asyncio.run(_process_hourly_nurture())
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Hourly Nurture Job Failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60)

async def _process_hourly_nurture():
    """
    Hourly Metronome Job.
    Checks for users who need Morning Rashi or Evening Nurture.
    """
    async with get_db_context() as db:
        try:
            now_utc = datetime.now(timezone.utc)
            logger.info(f"Starting Hourly Nurture Check at {now_utc}")
            
            # 1. Fetch Candidates
            # Users where next_rashi_at <= now OR next_nurture_at <= now
            # Limit to batch size (e.g. 100) and loop? 
            # For MVP, fetch all (assuming small user base)
            # Or use pagination loops.
            
            stmt = select(User).where(
                or_(
                    User.next_rashi_at <= now_utc,
                    User.next_nurture_at <= now_utc
                )
            ).limit(500) # Batch size safety
            
            result = await db.execute(stmt)
            users = result.scalars().all()
            
            logger.info(f"Found {len(users)} users for processing")
            
            nurture_service = NurtureService(db)
            rashi_service = RashiphalaluService(db) # Assume this exists
            
            processed_rashi = 0
            processed_nurture = 0
            
            for user in users:
                try:
                    # Check Rashi
                    if user.next_rashi_at and user.next_rashi_at <= now_utc:
                        # Send Rashi
                        await rashi_service.send_daily_rashi_to_user(user)
                        logger.info(f"Sent Rashi to {user.phone}")
                        
                        # Update Schedule (Add 24h)
                        user.next_rashi_at += timedelta(days=1)
                        processed_rashi += 1
                        
                    # Check Nurture
                    if user.next_nurture_at and user.next_nurture_at <= now_utc:
                        # Send Nurture
                        await nurture_service.process_nurture_for_user(user)
                        
                        # Update Schedule (Handled inside process_nurture_for_user? logic is cleaner there)
                        # Wait, NurtureService advances state. 
                        # Does it advance next_nurture_at? Yes.
                        processed_nurture += 1
                        
                except Exception as e:
                    logger.error(f"Error processing user {user.id}: {e}")
                    continue
            
            await db.commit()
            logger.info(f"Hourly Check Complete. Rashi: {processed_rashi}, Nurture: {processed_nurture}")
            
        except Exception as e:
            logger.error(f"Hourly Nurture Job Failed: {e}", exc_info=True)
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(process_hourly_nurture())
