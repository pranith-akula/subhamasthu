"""
User Service - User CRUD and state management.
"""

import uuid
import logging
from typing import Optional, List
from datetime import datetime, date, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.conversation import Conversation
from app.fsm.states import ConversationState

logger = logging.getLogger(__name__)


class UserService:
    """Service for user management and state tracking."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_or_create_user(
        self,
        phone: str,
        name: Optional[str] = None,
    ) -> User:
        """Get existing user or create new one."""
        # Normalize phone number
        phone = self._normalize_phone(phone)
        
        # Try to find existing user (with row locking)
        result = await self.db.execute(
            select(User).where(User.phone == phone).with_for_update()
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Update name if provided and not set
            if name and not user.name:
                user.name = name
            return user
        
        # Create new user
        user = User(
            phone=phone,
            name=name,
            state=ConversationState.NEW.value,
        )
        self.db.add(user)
        await self.db.flush()
        
        # Create conversation record
        conversation = Conversation(
            user_id=user.id,
            state=ConversationState.NEW.value,
        )
        self.db.add(conversation)
        await self.db.flush()
        
        logger.info(f"Created new user: {phone}")
        return user
    
    async def get_user_by_phone(self, phone: str) -> Optional[User]:
        """Get user by phone number."""
        phone = self._normalize_phone(phone)
        result = await self.db.execute(
            select(User).where(User.phone == phone)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_user_state(
        self,
        user: User,
        new_state: ConversationState,
    ) -> User:
        """Update user's conversation state."""
        old_state = user.state
        user.state = new_state.value
        user.updated_at = datetime.utcnow()
        
        # Also update conversation record
        result = await self.db.execute(
            select(Conversation).where(Conversation.user_id == user.id)
        )
        conversation = result.scalar_one_or_none()
        if conversation:
            conversation.state = new_state.value
            conversation.updated_at = datetime.utcnow()
        
        logger.info(f"User {user.phone} state: {old_state} -> {new_state.value}")
        return user
    
    async def set_user_name(self, user: User, name: str) -> User:
        """Set user's name preference."""
        user.name = name
        user.updated_at = datetime.utcnow()
        return user
    
    async def set_user_rashi(self, user: User, rashi: str) -> User:
        """Set user's rashi preference (MANDATORY)."""
        user.rashi = rashi
        user.updated_at = datetime.utcnow()
        return user
    
    async def set_user_nakshatra(self, user: User, nakshatra: str) -> User:
        """Set user's janam nakshatra (OPTIONAL)."""
        user.nakshatra = nakshatra
        user.updated_at = datetime.utcnow()
        return user
    
    async def set_user_birth_time(self, user: User, birth_time: str) -> User:
        """Set user's birth time (OPTIONAL). Format: HH:MM in 24-hour."""
        user.birth_time = birth_time
        user.updated_at = datetime.utcnow()
        return user
    
    async def set_user_deity(self, user: User, deity: str) -> User:
        """Set user's preferred deity."""
        user.preferred_deity = deity
        user.updated_at = datetime.now(timezone.utc)
        return user
    
    async def set_user_auspicious_day(self, user: User, day: str) -> User:
        """Set user's preferred auspicious day."""
        user.auspicious_day = day
        user.updated_at = datetime.now(timezone.utc)
        return user
    
    async def set_user_dob(self, user: User, dob: date) -> User:
        """Set user's date of birth."""
        user.dob = dob
        user.updated_at = datetime.now(timezone.utc)
        return user
        
    async def set_user_wedding_anniversary(self, user: User, anniversary: date) -> User:
        """Set user's wedding anniversary."""
        user.wedding_anniversary = anniversary
        user.updated_at = datetime.now(timezone.utc)
        return user
    
    async def set_last_sankalp(self, user: User) -> User:
        """Set last sankalp timestamp (starts cooldown)."""
        user.last_sankalp_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        
        # Also counts as engagement
        await self.record_engagement(user)
        return user
    
    async def record_engagement(self, user: User) -> None:
        """
        Record user engagement, update last_engagement_at and manage streak.
        Logic:
        - If last_engagement was yesterday: Increment streak.
        - If last_engagement was today: Do nothing to streak.
        - Otherwise: Reset streak to 1.
        """
        now = datetime.now(timezone.utc)
        
        if user.last_engagement_at:
            last_date = user.last_engagement_at.date()
            today_date = now.date()
            
            if last_date == today_date:
                # Already engaged today, just update timestamp
                user.last_engagement_at = now
                return
            
            if last_date == today_date - timedelta(days=1):
                # Consecutive day!
                user.streak_days += 1
            else:
                # Streak broken
                user.streak_days = 1
        else:
            # First engagement ever
            user.streak_days = 1
            
        user.last_engagement_at = now
        user.updated_at = now # Ensure timestamp update
        
        self.db.add(user)
        await self.db.commit()
        
        logger.debug(f"Recorded engagement for {user.phone}. Streak: {user.streak_days}")
    
    async def is_duplicate_message(
        self,
        user_id: uuid.UUID,
        message_id: str,
    ) -> bool:
        """Check if message is duplicate (for idempotency)."""
        # Redis check (Fast path)
        try:
            from app.redis import get_redis
            redis = await get_redis()
            
            cache_key = f"subhamasthu:msg:{user_id}:{message_id}"
            if await redis.exists(cache_key):
                return True
                
        except Exception:
            # Fallback if Redis fails
            pass
        
        # Check conversation record (DB is source of truth)
        result = await self.db.execute(
            select(Conversation).where(Conversation.user_id == user_id)
        )
        conversation = result.scalar_one_or_none()
        
        if conversation and conversation.last_inbound_msg_id == message_id:
            # If in DB but not Redis (expired or restart), populate Redis
            try:
                if 'redis' in locals():
                    await redis.setex(cache_key, 86400, "1")
            except Exception:
                pass
            return True
        
        # Update last message ID
        if conversation:
            conversation.last_inbound_msg_id = message_id
        
        # Add to Redis (24h TTL)
        try:
            if 'redis' in locals():
                await redis.setex(cache_key, 86400, "1")
        except Exception:
            pass
        
        return False
    
    async def get_active_users_by_rashi(self, rashi: str) -> list[User]:
        """Get all onboarded users with a specific rashi."""
        result = await self.db.execute(
            select(User)
            .where(User.rashi == rashi)
            .where(User.state.not_in([
                ConversationState.NEW.value,
                ConversationState.WAITING_FOR_RASHI.value,
                ConversationState.WAITING_FOR_NAKSHATRA.value,
                ConversationState.WAITING_FOR_BIRTH_TIME.value,
                ConversationState.WAITING_FOR_DEITY.value,
                ConversationState.WAITING_FOR_AUSPICIOUS_DAY.value,
            ]))
        )
        return list(result.scalars().all())
    
    async def get_users_for_weekly_prompt(self, day_of_week: str) -> list[User]:
        """Get users whose auspicious day is today and not in cooldown."""
        from datetime import timedelta
        
        # ISO Week Logic: Reset eligibility on Monday
        # If last_sankalp_at is in previous week (before this week's Monday 00:00), they are eligible.
        today = datetime.utcnow()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = await self.db.execute(
            select(User)
            .where(User.auspicious_day == day_of_week)
            .where(
                (User.last_sankalp_at == None) |  # noqa: E711
                (User.last_sankalp_at < start_of_week)
            )
            .where(User.state.in_([
                ConversationState.DAILY_PASSIVE.value,
                ConversationState.ONBOARDED.value,
            ]))
        )
        return list(result.scalars().all())
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number (remove spaces, dashes)."""
        return "".join(c for c in phone if c.isdigit())
