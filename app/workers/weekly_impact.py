"""
Weekly Impact Summary Worker.

Sends weekly impact summary to all active users on Sunday 10 AM IST.
"""

import asyncio
import logging

from app.workers.celery_app import celery_app
from app.database import get_db_context

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def send_weekly_impact_summary(self):
    """
    Celery task to send weekly impact summary.
    
    Runs Sunday 10:00 AM IST.
    Sends scoreboard-style message to all active users.
    """
    try:
        result = asyncio.run(_send_weekly_summary())
        logger.info(f"Weekly impact summary sent: {result}")
        return result
    except Exception as e:
        logger.error(f"Weekly impact summary failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


async def _send_weekly_summary():
    """Async implementation of weekly summary sending."""
    from app.services.impact_service import ImpactService
    from app.services.user_service import UserService
    from app.services.meta_whatsapp_service import MetaWhatsappService
    from app.fsm.states import ConversationState
    
    async with get_db_context() as db:
        # Get weekly data
        impact_service = ImpactService(db)
        weekly_data = await impact_service.get_weekly_summary_data()
        
        devotees = weekly_data["devotees"]
        meals = weekly_data["meals"]
        cities = weekly_data["cities"]
        
        # Skip if no activity this week
        if meals == 0:
            logger.info("No seva activity this week, skipping summary")
            return {"sent": 0, "skipped": "no_activity"}
        
        # Get all active users
        user_service = UserService(db)
        from sqlalchemy import select
        from app.models.user import User
        
        result = await db.execute(
            select(User)
            .where(User.state.in_([
                ConversationState.DAILY_PASSIVE.value,
                ConversationState.ONBOARDED.value,
            ]))
        )
        users = list(result.scalars().all())
        
        whatsapp = MetaWhatsappService()
        sent = 0
        
        for user in users:
            try:
                # Get personal impact
                personal = await impact_service.get_user_impact(user.id)
                personal_meals = personal["lifetime_meals"]
                
                # Send template with scoreboard + personal count
                # Template params: [devotees, meals, cities, personal_meals]
                await whatsapp.send_template_message(
                    phone=user.phone,
                    template_id="weekly_impact_summary",
                    params=[
                        str(devotees),
                        str(meals),
                        str(cities),
                        str(personal_meals),
                    ]
                )
                sent += 1
                
            except Exception as e:
                logger.error(f"Failed to send summary to {user.phone}: {e}")
        
        return {"sent": sent, "total_users": len(users)}
