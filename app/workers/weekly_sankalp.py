"""
Weekly Sankalp Worker.
Sends weekly sankalp prompts to eligible users.
"""

import asyncio
import logging

from app.workers.celery_app import celery_app
from app.database import get_db_context
from app.services.sankalp_service import SankalpService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def send_weekly_sankalp_prompts(self):
    """
    Celery task to send weekly sankalp prompts.
    
    Runs daily at 7:30 AM CST, sends prompts to users
    whose auspicious_day matches today.
    """
    try:
        result = asyncio.run(_send_weekly_prompts())
        logger.info(f"Weekly sankalp prompts sent: {result}")
        return result
    except Exception as e:
        logger.error(f"Weekly sankalp prompts failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


async def _send_weekly_prompts():
    """Async implementation of weekly prompt sending."""
    async with get_db_context() as db:
        service = SankalpService(db)
        sent = await service.send_weekly_prompts()
        return {"sent": sent}


@celery_app.task(bind=True)
def send_prompt_to_user(self, user_id: str):
    """
    Send weekly sankalp prompt to a specific user.
    
    Args:
        user_id: UUID of the user
    """
    import uuid
    
    try:
        user_uuid = uuid.UUID(user_id)
        asyncio.run(_send_prompt_to_user(user_uuid))
        logger.info(f"Sent weekly prompt to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send prompt to {user_id}: {e}")
        raise


async def _send_prompt_to_user(user_uuid):
    """Async implementation of sending prompt to specific user."""
    from app.services.user_service import UserService
    
    async with get_db_context() as db:
        user_service = UserService(db)
        user = await user_service.get_user_by_id(user_uuid)
        
        if not user:
            logger.warning(f"User {user_uuid} not found")
            return
        
        sankalp_service = SankalpService(db)
        await sankalp_service.send_reflection_prompt(user)
