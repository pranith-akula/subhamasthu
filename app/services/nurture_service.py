
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload

from app.models.user import User
from app.models.sankalp import Sankalp, SankalpStatus
from app.services.meta_whatsapp_service import MetaWhatsappService
from app.config import settings

logger = logging.getLogger(__name__)

class NurtureService:
    """
    Service to handle the 28-Day Trust Engine cycle.
    - Manages 3 Tracks: DEVOTION, FAMILY (SECURITY), CAREER (GROWTH).
    - Sends daily content based on user.nurture_day.
    - Handles Surprise Days and Sankalp Invites.
    """
    
    # 28-Day Content Map
    # Structure: {day: {track: {type, content}}}
    # Use placeholders for now.
    CONTENT_LIBRARY = {
        1: {
            "DEVOTION": {"type": "text", "body": "Welcome to Subhamasthu. We are a small community dedicated to preserving Dharma."},
            "SECURITY": {"type": "text", "body": "Welcome. May the divine protect your home and family."},
            "GROWTH": {"type": "text", "body": "Welcome. True growth begins with inner alignment."},
        },
        # ... Add more days
        7: {
             "type": "sankalp_invite", 
             "body": "This Sunday, we are offering Sankalp inclusion. If your name should be included, you may join."
        },
        # ...
    }

    def __init__(self, db: AsyncSession):
        self.db = db
        self.whatsapp = MetaWhatsappService()

    async def process_nurture_for_user(self, user: User) -> bool:
        """
        Process the daily nurture step for a single user.
        Called by the Hourly Worker when next_nurture_at <= Now.
        """
        try:
            logger.info(f"Processing nurture for user {user.phone}, Day {user.nurture_day}, Track {user.nurture_track}")
            
            # 1. Get Content
            content = self._get_content(user.nurture_day, user.nurture_track)
            
            # 2. Check Logic (Sankalp Invite vs Rest)
            if user.nurture_day in [7, 28]: # Week 1 & 4 Sundays
                 if self._should_send_invite(user):
                     await self._send_sankalp_invite(user)
                 else:
                     await self._send_rest_message(user)
            elif user.nurture_day == user.surprise_day:
                 await self._send_surprise_blessing(user)
            elif content:
                 await self._send_content(user, content)
            
            # 3. Advance State
            await self._advance_user_state(user)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process nurture for {user.phone}: {e}", exc_info=True)
            return False

    def _get_content(self, day: int, track: str) -> Optional[Dict]:
        """Retrieve content from library."""
        day_content = self.CONTENT_LIBRARY.get(day)
        if not day_content:
            return None
            
        # If track specific exists
        if track in day_content:
            return day_content[track]
        # If generic (e.g. "type": "sankalp_invite" at top level)
        if "type" in day_content:
            return day_content
            
        return day_content.get("DEVOTION") # Fallback

    def _should_send_invite(self, user: User) -> bool:
        """Check safeguards."""
        # Anti-predatory: Max 2 sankalps in 28-day cycle
        if user.sankalps_in_cycle >= 2:
            return False
        return True

    async def _send_content(self, user: User, content: Dict):
        """Send message via WhatsApp."""
        if content["type"] == "text":
            await self.whatsapp.send_text_message(user.phone, content["body"])
        elif content["type"] == "image":
             # Need media ID or URL
             pass 

    async def _send_sankalp_invite(self, user: User):
        """Send soft invite."""
        logger.info(f"Sending Sankalp Invite to {user.phone}")
        # Send interactive message with buttons
        # ...

    async def _send_rest_message(self, user: User):
        """Send rest/blessing message."""
        await self.whatsapp.send_text_message(user.phone, "This Sunday, rest in the knowledge that you are supported.")

    async def _send_surprise_blessing(self, user: User):
        """Send surprise."""
        await self.whatsapp.send_text_message(user.phone, "Surprise! A special Archana was performed in your name today. No action needed. Just receive.")

    async def _advance_user_state(self, user: User):
        """Update DB timestamps and counters."""
        # Increment day
        user.nurture_day += 1
        if user.nurture_day > 28:
            user.nurture_day = 1
            user.sankalps_in_cycle = 0 # Reset cycle counter
            import random
            user.surprise_day = random.randint(14, 20) # New surprise day
            
        # Update next_nurture_at (Add 24 hours to PREVIOUS schedule to maintain time)
        # Or recalculate from TZ? Safer to add 24h if schedule was correct.
        if user.next_nurture_at:
             user.next_nurture_at += timedelta(days=1)
        else:
             # Fallback
             pass
             
        user.last_nurture_sent_at = datetime.now(timezone.utc)
        
        await self.db.flush() # Caller commits
