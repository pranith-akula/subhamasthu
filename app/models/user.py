"""User model - core user data and preferences."""

import uuid
from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy import String, DateTime, Date, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.fsm.states import ConversationState, Rashi, Deity, AuspiciousDay


class User(Base):
    """
    User table storing phone, preferences, and state.
    One user per phone number.
    """
    
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # WhatsApp phone number (unique identifier)
    phone: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        nullable=False,
        index=True,
    )
    
    # User name (collected during onboarding or from WhatsApp profile)
    name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Rashi preference for daily Rashiphalalu (MANDATORY)
    rashi: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Janam Nakshatra - birth star (OPTIONAL)
    nakshatra: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Birth time for more personalized content (OPTIONAL)
    # Format: HH:MM in 24-hour format
    birth_time: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    
    # Preferred deity for sankalp
    preferred_deity: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Preferred auspicious day for weekly sankalp trigger
    auspicious_day: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    
    # User timezone (default: America/Chicago for DFW)
    tz: Mapped[str] = mapped_column(
        String(50),
        default="America/Chicago",
        nullable=False,
    )
    
    # Current conversation state
    state: Mapped[str] = mapped_column(
        String(50),
        default=ConversationState.NEW.value,
        nullable=False,
    )
    
    # Last sankalp timestamp (for cooldown enforcement)
    last_sankalp_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Onboarding completion timestamp
    onboarded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Personal Dates (Phase 2)
    dob: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    wedding_anniversary: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Count of Rashiphalalu messages sent (for 6-day eligibility)
    rashiphalalu_days_sent: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    
    # Record timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<User {self.phone} state={self.state}>"
    
    @property
    def is_onboarded(self) -> bool:
        """Check if user has completed onboarding."""
        return self.state not in [
            ConversationState.NEW.value,
            ConversationState.WAITING_FOR_RASHI.value,
            ConversationState.WAITING_FOR_NAKSHATRA.value,
            ConversationState.WAITING_FOR_BIRTH_TIME.value,
            ConversationState.WAITING_FOR_DEITY.value,
            ConversationState.WAITING_FOR_AUSPICIOUS_DAY.value,
        ]
    
    @property
    def is_in_cooldown(self) -> bool:
        """Check if user is in 7-day cooldown period."""
        if not self.last_sankalp_at:
            return False
        
        from datetime import timedelta
        cooldown_end = self.last_sankalp_at + timedelta(days=7)
        return datetime.utcnow() < cooldown_end
    
    @property
    def is_eligible_for_sankalp(self) -> bool:
        """
        Check if user is eligible to receive Sankalp prompt.
        Requires 6+ days of Rashiphalalu and no active cooldown.
        """
        return (
            self.is_onboarded and
            self.rashiphalalu_days_sent >= 6 and
            not self.is_in_cooldown
        )
