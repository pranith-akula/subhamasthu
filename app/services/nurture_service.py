
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload

from app.models.user import User
from app.models.sankalp import Sankalp, SankalpStatus
from app.models.message_log import MessageLog, MessageType, MessageStatus
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
    # 28-Day Theme Map for Dynamic Generation
    THEME_MAP = {
        # Week 1: Identity & Belonging
        1: "Welcome & Identity: Affirm they made a good choice. Focus on Peace/Protection/Growth.",
        2: "Proof of Impact: Describe the specific impact of their support (Annadanam/Temples). Visually descriptive.",
        3: "Wisdom: A short, deep quote or insight from scriptures relevant to their track.",
        4: "Application: A small, easy spiritual practice (Chant/Lamp/Task) for today.",
        5: "Impact: A story of a beneficiary or temple that was helped. Emotional connection.",
        6: "Preparation: Preparing the mind for the upcoming Sankalp/Ritual.",
        7: "INVITE: Invitation to the weekly Sankalp (Gratitude/Protection/Removal of Obstacles).",

        # Week 2: Transparency & Connection
        8: "Gratitude: Thank them for being part of the family. Deep appreciation.",
        9: "Faith/Resilience: A message about holding on during tough times.",
        10: "Silence/Presence: Encouraging a moment of mindfulness or family connection.",
        11: "Valid Mythology: A short story element from Ramayana/Mahabharata illustrating the track theme.",
        12: "Direct Impact: 'Because of you...' specific example of service.",
        13: "Inner Thought: A question for self-reflection.",
        14: "Rest: Permission to rest and let the Divine take over.",

        # Week 3: Deepening
        15: "Surrender: The concept of Sharanagati (surrender) to God/Universe.",
        16: "Ritual: A simple home ritual suggestion (Threshold/Water/Flower).",
        17: "COLLECTIVE PRAYER: Inform them that during temple seva, we included all Subhamasthu families in prayer. (Community feeling).",
        18: "Feeling the Shift: Asking if they feel the difference/peace.",
        19: "Story of Grace: A story where grace intervened impossible odds.",
        20: "Service: How their existence helps others.",
        21: "Rest: Spiritual recharge.",

        # Week 4: Commitment
        22: "Consistency: The power of small daily habits.",
        23: "Mantra: A specific mantra for their track (Shanti/Mangala/Gam).",
        24: "Awakening: Waking up the inner spirit/potential.",
        25: "Rising Energy: Preparing for the month-end transition.",
        26: "Final Thought: Summarizing the journey of the month.",
        27: "Preparation: Ready for the final seal of the month.",
        28: "INVITE: Monthly Sankalp Invitation (Gratitude/Protection/Prosperity).",
    }
    
    SYSTEM_PROMPT = """You are a warm, wise, and spiritual guide for 'Subhamasthu', a Vedic community.
    Your goal is to nurture the user based on their specific 'Track' and the daily 'Theme'.
    
    Tracks:
    - DEVOTION: Focus on Bhakti, peace, connection to God.
    - SECURITY: Focus on family protection, health, safety, ancestors.
    - GROWTH: Focus on career, overcoming obstacles, success, focus.
    
    Guidelines:
    - Keep it short (2-3 sentences max). WhatsApp friendly.
    - Tone: Warm, diverse, non-judgmental, inclusive, authentic.
    - NO generic "Namaste" or flowery language. Be grounded.
    - For 'INVITE' days, include a clear call to action for the Sankalp buttons.
    - For 'SURPRISE' days, sound genuinely excited about the gift given to them.
    - English language, but approachable.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.whatsapp = MetaWhatsappService()
        self.openai_client = None
        if settings.openai_api_key:
             from openai import AsyncOpenAI
             self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def _get_content(self, day: int, track: str, user_name: str = "Devotee") -> Optional[Dict]:
        """Generate content dynamically via LLM."""
        theme = self.THEME_MAP.get(day)
        if not theme:
            return None
            
        # Hardcoded types for structure
        msg_type = "text"
        if day in [7, 28]:
            msg_type = "sankalp_invite"
            
        if not self.openai_client:
            logger.warning("OpenAI client not initialized, using fallback.")
            return {"type": "text", "body": f"Namaste {user_name}. Day {day} blessings to you."}

        try:
            prompt = f"""
            User Name: {user_name}
            Track: {track}
            Day: {day}
            Theme/Instruction: {theme}
            
            Write the message body.
            """
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o", # Or gpt-3.5-turbo
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            body = response.choices[0].message.content.strip()
            # Clean up quotes if any
            body = body.replace('"', '').replace("'", "")
            
            if msg_type == "sankalp_invite":
                 return {
                     "type": "sankalp_invite", 
                     "body": body,
                     "buttons": ["$21 (Dharmika)", "$51 (Punya Vriddhi)", "$108 (Maha Sankalp)"]
                 }
                 
            return {"type": "text", "body": body}

        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            return {"type": "text", "body": f"Namaste {user_name}. May this day bring you peace and focus. (Day {day})"}

    async def process_nurture_for_user(self, user: User) -> bool:
        """
        Process the daily nurture step for a single user.
        Called by the Hourly Worker when next_nurture_at <= Now.
        """
        try:
            now_utc = datetime.now(timezone.utc)
            idempotency_key = f"nurture_{now_utc.date()}_{user.id}"
            
            # 0. Idempotency Check (Strategic Opt)
            query = select(MessageLog).where(MessageLog.idempotency_key == idempotency_key)
            result = await self.db.execute(query)
            if result.scalar_one_or_none():
                logger.warning(f"Skipping duplicate nurture for {user.phone}: {idempotency_key}")
                return True

            logger.info(f"Processing nurture for user {user.phone}, Day {user.nurture_day}, Track {user.nurture_track}")
            
            # 1. Get Content
            content = await self._get_content(user.nurture_day, user.nurture_track, user.name or "Devotee")
            
            # 2. Check Logic (Sankalp Invite vs Rest)
            if user.nurture_day in [7, 28]: # Week 1 & 4 Sundays
                 if self._should_send_invite(user):
                     await self._send_sankalp_invite(user, content)
                 else:
                     await self._send_rest_message(user)
            elif user.nurture_day == user.surprise_day:
                 await self._send_surprise_blessing(user)
            elif content:
                 await self._send_content(user, content)
            
            # 3. Log Success
            msg_log = MessageLog(
                user_id=user.id,
                message_type=MessageType.NURTURE,
                content_preview=str(content.get("type", "unknown")),
                status=MessageStatus.SENT,
                idempotency_key=idempotency_key
            )
            self.db.add(msg_log)
            
            # 4. Advance State
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

    async def _send_sankalp_invite(self, user: User, content: Dict):
        """Send soft invite."""
        logger.info(f"Sending Sankalp Invite to {user.phone}")
        
        buttons_data = []
        for btn_label in content.get("buttons", ["$21 (Dharmika)", "$51 (Punya Vriddhi)", "$108 (Maha Sankalp)"]):
             # Extract amount for ID? e.g. "sankalp_21"
             # Assuming label is like "$21 (Archana)" or just "$21"
             clean_label = btn_label.split(" ")[0].replace("$", "").replace("₹", "")
             buttons_data.append({
                 "id": f"sankalp_invite_{clean_label}",
                 "title": btn_label[:20] # Max 20 chars
             })
             
        await self.whatsapp.send_button_message(
            phone=user.phone,
            body_text=content["body"],
            buttons=buttons_data
        )

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
