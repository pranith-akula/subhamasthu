"""
Daily Rashiphalalu Worker.
Generates and broadcasts daily horoscope messages.
"""

import asyncio
import logging

from app.workers.celery_app import celery_app
from app.database import get_db_context
from app.services.rashiphalalu_service import RashiphalaluService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def broadcast_daily_rashiphalalu(self):
    """
    Celery task to generate and broadcast daily Rashiphalalu.
    
    Runs daily at 7:00 AM CST.
    """
    try:
        # Run async code in event loop
        asyncio.run(_broadcast_daily_rashiphalalu())
        logger.info("Daily Rashiphalalu broadcast completed")
    except Exception as e:
        logger.error(f"Daily Rashiphalalu broadcast failed: {e}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


async def _broadcast_daily_rashiphalalu():
    """Async implementation of daily broadcast."""
    async with get_db_context() as db:
        service = RashiphalaluService(db)
        
        # Generate messages for all rashis
        generated = await service.generate_daily_messages()
        logger.info(f"Generated {generated} Rashiphalalu messages")
        
        # Broadcast to users
        sent = await service.broadcast_to_users()
        logger.info(f"Sent {sent} Rashiphalalu messages")
        
        return {"generated": generated, "sent": sent}


@celery_app.task(bind=True)
def generate_rashiphalalu_for_date(self, date_str: str):
    """
    Generate Rashiphalalu for a specific date (for pre-generation).
    
    Args:
        date_str: Date in YYYY-MM-DD format
    """
    from datetime import datetime
    
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        asyncio.run(_generate_for_date(target_date))
        logger.info(f"Generated Rashiphalalu for {date_str}")
    except Exception as e:
        logger.error(f"Rashiphalalu generation failed for {date_str}: {e}")
        raise


async def _generate_for_date(target_date):
    """Async implementation of generation for specific date."""
    async with get_db_context() as db:
        service = RashiphalaluService(db)
        generated = await service.generate_daily_messages(target_date)
        return generated
