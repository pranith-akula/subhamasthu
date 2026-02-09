"""
Post-Conversion Follow-up Worker.

Runs hourly to process pending follow-up messages.
"""

import logging
from app.workers.celery_app import celery_app
from app.database import get_db_context

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def process_follow_ups(self):
    """
    Process pending post-conversion follow-ups.
    
    Runs hourly to send Day 3 and Day 7 messages.
    """
    import asyncio
    
    async def run():
        async with get_db_context() as db:
            from app.services.post_conversion import PostConversionService
            
            service = PostConversionService(db)
            count = await service.process_pending_follow_ups()
            
            return count
    
    try:
        count = asyncio.run(run())
        logger.info(f"Processed {count} follow-up messages")
        return {"success": True, "count": count}
    except Exception as e:
        logger.error(f"Follow-up processing failed: {e}")
        self.retry(exc=e, countdown=60)
