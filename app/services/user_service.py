"""
User Service - User CRUD and state management.
"""

import uuid
import logging
from typing import Optional
from datetime import datetime

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
        self._message_cache: set = set()  # In-memory cache for quick dedup
    
    async def get_or_create_user(
        self,
        phone: str,
        name: Optional[str] = None,
    ) -> User:
        """Get existing user or create new one."""
        # Normalize phone number
        phone = self._normalize_phone(phone)
        
        # Try to find existing user
        result = await self.db.execute(
            select(User).where(User.phone == phone)
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
        user.updated_at = datetime.utcnow()
        return user
    
    async def set_user_auspicious_day(self, user: User, day: str) -> User:
        """Set user's preferred auspicious day."""
        user.auspicious_day = day
        user.updated_at = datetime.utcnow()
        return user
    
    async def set_last_sankalp(self, user: User) -> User:
        """Set last sankalp timestamp (starts cooldown)."""
        user.last_sankalp_at = datetime.utcnow()
        user.updated_at = datetime.utcnow()
        return user
    
    async def is_duplicate_message(
        self,
        user_id: uuid.UUID,
        message_id: str,
    ) -> bool:
        """Check if message is duplicate (for idempotency)."""
        # Quick in-memory check
        cache_key = f"{user_id}:{message_id}"
        if cache_key in self._message_cache:
            return True
        
        # Check conversation record
        result = await self.db.execute(
            select(Conversation).where(Conversation.user_id == user_id)
        )
        conversation = result.scalar_one_or_none()
        
        if conversation and conversation.last_inbound_msg_id == message_id:
            return True
        
        # Update last message ID
        if conversation:
            conversation.last_inbound_msg_id = message_id
        
        # Add to cache
        self._message_cache.add(cache_key)
        
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
        
        cooldown_cutoff = datetime.utcnow() - timedelta(days=7)
        
        result = await self.db.execute(
            select(User)
            .where(User.auspicious_day == day_of_week)
            .where(
                (User.last_sankalp_at == None) |  # noqa: E711
                (User.last_sankalp_at < cooldown_cutoff)
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
