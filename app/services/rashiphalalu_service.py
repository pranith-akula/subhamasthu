"""
Rashiphalalu Service - Daily horoscope generation and broadcasting.
"""

import logging
from datetime import date, datetime
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import openai

from app.config import settings
from app.models.rashiphalalu import RashiphalaluCache
from app.models.user import User
from app.fsm.states import Rashi
from app.services.gupshup_service import GupshupService

logger = logging.getLogger(__name__)

# OpenAI client
openai.api_key = settings.openai_api_key


class RashiphalaluService:
    """Service for generating and broadcasting daily Rashiphalalu."""
    
    PROMPT_VERSION = "v1"
    MODEL = "gpt-4o-mini"
    
    # Prompt template for generating Rashiphalalu
    SYSTEM_PROMPT = """You are a spiritual advisor writing daily Rashiphalalu (horoscope) messages for Telugu-speaking NRI families in the US.

Your messages should:
1. Be in Telugu-English mix (Tenglish) - primarily English with Telugu words for spiritual terms
2. Be hope-oriented and reassuring, NEVER deterministic or fear-inducing
3. Include a greeting appropriate for the day
4. Optionally mention tithi/panchang context
5. Give rashi-specific gentle guidance
6. End with a dharmic quote or wisdom
7. Be 3-4 sentences, warm and devotional in tone
8. NEVER mention payments, donations, or any commercial elements

Example format:
"🙏 Shubhodayam! [Day] roju [Rashi] vaalaku manchiga untundi. [Gentle guidance]. [Dharmic quote]."
"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gupshup = GupshupService()
    
    async def generate_daily_messages(self, target_date: Optional[date] = None) -> int:
        """
        Generate Rashiphalalu for all 12 rashis for the given date.
        
        Returns count of messages generated.
        """
        if target_date is None:
            target_date = date.today()
        
        generated = 0
        
        for rashi in Rashi:
            # Check if already generated
            existing = await self._get_cached_message(target_date, rashi.value)
            if existing:
                logger.debug(f"Rashiphalalu for {rashi.value} on {target_date} already exists")
                continue
            
            # Generate via OpenAI
            message = await self._generate_for_rashi(target_date, rashi)
            
            if message:
                # Cache the message
                cache_entry = RashiphalaluCache(
                    date=target_date,
                    rashi=rashi.value,
                    language_variant="te_en",
                    message_text=message,
                    model=self.MODEL,
                    prompt_version=self.PROMPT_VERSION,
                )
                self.db.add(cache_entry)
                generated += 1
        
        await self.db.flush()
        logger.info(f"Generated {generated} Rashiphalalu messages for {target_date}")
        return generated
    
    async def broadcast_to_users(self, target_date: Optional[date] = None) -> int:
        """
        Broadcast Rashiphalalu to all active users based on their rashi.
        
        Returns count of messages sent.
        """
        if target_date is None:
            target_date = date.today()
        
        sent = 0
        
        for rashi in Rashi:
            # Get cached message
            message = await self._get_cached_message(target_date, rashi.value)
            if not message:
                logger.warning(f"No cached message for {rashi.value} on {target_date}")
                continue
            
            # Get users with this rashi
            users = await self._get_users_by_rashi(rashi.value)
            
            for user in users:
                try:
                    msg_id = await self.gupshup.send_text_message(
                        phone=user.phone,
                        message=message,
                    )
                    if msg_id:
                        sent += 1
                except Exception as e:
                    logger.error(f"Failed to send to {user.phone}: {e}")
        
        logger.info(f"Broadcast complete: {sent} messages sent")
        return sent
    
    async def get_message_for_user(self, user: User, target_date: Optional[date] = None) -> Optional[str]:
        """Get the Rashiphalalu message for a specific user."""
        if not user.rashi:
            return None
        
        if target_date is None:
            target_date = date.today()
        
        return await self._get_cached_message(target_date, user.rashi)
    
    async def _generate_for_rashi(self, target_date: date, rashi: Rashi) -> Optional[str]:
        """Generate Rashiphalalu for a specific rashi using OpenAI."""
        day_name = target_date.strftime("%A")
        
        user_prompt = f"""Generate today's Rashiphalalu for {rashi.value} ({rashi.telugu_name}).

Date: {target_date.strftime("%B %d, %Y")} ({day_name})
Rashi: {rashi.value} ({rashi.telugu_name})

Write a warm, hope-oriented message in Telugu-English mix."""
        
        try:
            response = await openai.ChatCompletion.acreate(
                model=self.MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=200,
                temperature=0.7,
            )
            
            message = response.choices[0].message.content.strip()
            logger.debug(f"Generated for {rashi.value}: {message[:50]}...")
            return message
            
        except Exception as e:
            logger.error(f"OpenAI generation failed for {rashi.value}: {e}")
            return None
    
    async def _get_cached_message(self, target_date: date, rashi: str) -> Optional[str]:
        """Get cached message from database."""
        result = await self.db.execute(
            select(RashiphalaluCache)
            .where(RashiphalaluCache.date == target_date)
            .where(RashiphalaluCache.rashi == rashi)
            .where(RashiphalaluCache.language_variant == "te_en")
        )
        cache = result.scalar_one_or_none()
        return cache.message_text if cache else None
    
    async def _get_users_by_rashi(self, rashi: str) -> List[User]:
        """Get all active users with a specific rashi."""
        from app.fsm.states import ConversationState
        
        result = await self.db.execute(
            select(User)
            .where(User.rashi == rashi)
            .where(User.state.not_in([
                ConversationState.NEW.value,
                ConversationState.WAITING_FOR_RASHI.value,
                ConversationState.WAITING_FOR_DEITY.value,
                ConversationState.WAITING_FOR_AUSPICIOUS_DAY.value,
            ]))
        )
        return list(result.scalars().all())
