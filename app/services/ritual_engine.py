"""
RitualOrchestrator - Unified engine for ritual lifecycle management.

Responsibilities:
- Determine ritual phase based on user's cycle day
- Apply phase-aware cooldown rules
- Gate Maha Sankalp based on intensity score
- Add timing jitter for mystique
- Track analytics events
- Enforce max prompts per month
"""

import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.ritual_event import RitualEvent

logger = logging.getLogger(__name__)


class RitualPhase(str, Enum):
    """Ritual phases in 28-day cycle."""
    INITIATION = "INITIATION"  # Days 1-7: Full Sankalp
    BLESSING = "BLESSING"       # Days 8-14: Light Blessing
    SILENT = "SILENT"           # Days 15-21: Wisdom + Impact (no ask)
    MAHA = "MAHA"               # Days 22-28: Maha Sankalp (gated)


class EventType(str, Enum):
    """Types of ritual events for analytics."""
    SANKALP_PROMPT = "SANKALP_PROMPT"
    LIGHT_BLESSING = "LIGHT_BLESSING"
    SILENT_WISDOM = "SILENT_WISDOM"
    MAHA_SANKALP = "MAHA_SANKALP"
    CONVERSION = "CONVERSION"
    WISDOM_READ = "WISDOM_READ"
    IMPACT_VIEW = "IMPACT_VIEW"


class RitualOrchestrator:
    """
    Unified orchestrator for ritual lifecycle.
    
    Replaces fragmented cron jobs with single source of truth.
    """
    
    # Hard cap: Max 2 full sankalp prompts per month
    MAX_SANKALP_PROMPTS_PER_MONTH = 2
    
    # Minimum days between sankalp prompts
    MIN_DAYS_BETWEEN_PROMPTS = 6
    
    # Intensity threshold for Maha Sankalp eligibility
    MAHA_INTENSITY_THRESHOLD = 3
    
    # Jitter range for mystique (minutes)
    JITTER_RANGE = (-15, 15)
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    @staticmethod
    def get_ritual_phase(ritual_cycle_day: int) -> RitualPhase:
        """Determine ritual phase from cycle day (1-28)."""
        if ritual_cycle_day <= 7:
            return RitualPhase.INITIATION
        elif ritual_cycle_day <= 14:
            return RitualPhase.BLESSING
        elif ritual_cycle_day <= 21:
            return RitualPhase.SILENT
        else:
            return RitualPhase.MAHA
    
    @staticmethod
    def get_ritual_week(ritual_cycle_day: int) -> int:
        """Get week number (1-4) from cycle day."""
        return (ritual_cycle_day - 1) // 7 + 1
    
    def is_eligible_for_sankalp(self, user: User) -> Tuple[bool, str]:
        """
        Check if user is eligible for sankalp prompt.
        
        Phase-aware cooldown logic:
        - Only prompt on Week 1 (INITIATION) or Week 4 (MAHA)
        - Must wait at least 6 days since last prompt
        - Hard cap: 2 prompts per month
        
        Returns:
            (eligible, reason)
        """
        phase = self.get_ritual_phase(user.ritual_cycle_day)
        
        # Only prompt during INITIATION or MAHA phases
        if phase not in [RitualPhase.INITIATION, RitualPhase.MAHA]:
            return False, f"Not in eligible phase ({phase.value})"
        
        # Check monthly cap
        if user.sankalp_prompts_this_month >= self.MAX_SANKALP_PROMPTS_PER_MONTH:
            return False, "Monthly prompt cap reached"
        
        # Check cooldown
        if user.last_sankalp_prompt_at:
            days_since = (datetime.now(ZoneInfo("UTC")) - user.last_sankalp_prompt_at).days
            if days_since < self.MIN_DAYS_BETWEEN_PROMPTS:
                return False, f"Cooldown active ({days_since} days < {self.MIN_DAYS_BETWEEN_PROMPTS})"
        
        # For MAHA phase, check intensity score (behavioral gating)
        if phase == RitualPhase.MAHA:
            if user.ritual_intensity_score < self.MAHA_INTENSITY_THRESHOLD:
                return False, f"Intensity score too low ({user.ritual_intensity_score} < {self.MAHA_INTENSITY_THRESHOLD})"
        
        return True, "Eligible"
    
    def should_send_light_blessing(self, user: User) -> bool:
        """Check if user should receive light blessing (Week 2)."""
        return self.get_ritual_phase(user.ritual_cycle_day) == RitualPhase.BLESSING
    
    def should_send_silent_wisdom(self, user: User) -> bool:
        """Check if user should receive silent wisdom (Week 3)."""
        return self.get_ritual_phase(user.ritual_cycle_day) == RitualPhase.SILENT
    
    @staticmethod
    def get_trigger_time(base_time: datetime) -> datetime:
        """Add jitter (±15 min) to trigger time for mystique."""
        jitter_minutes = random.randint(-15, 15)
        return base_time + timedelta(minutes=jitter_minutes)
    
    @staticmethod
    def increment_cycle_day(user: User) -> int:
        """
        Increment ritual cycle day (1-28, wraps around).
        Also updates ritual_phase based on new day.
        
        Returns: New cycle day
        """
        new_day = user.ritual_cycle_day + 1
        if new_day > 28:
            new_day = 1
        
        user.ritual_cycle_day = new_day
        user.ritual_phase = RitualOrchestrator.get_ritual_phase(new_day).value
        
        return new_day
    
    @staticmethod
    def reset_monthly_counters(user: User) -> None:
        """Reset monthly counters (call on 1st of month)."""
        user.sankalp_prompts_this_month = 0
    
    @staticmethod
    def increment_intensity(user: User, points: int = 1) -> int:
        """
        Increment ritual intensity score.
        
        Points are awarded for:
        - Completing sankalp (+3)
        - Reading wisdom (+1)
        - Viewing impact (+1)
        """
        user.ritual_intensity_score = (user.ritual_intensity_score or 0) + points
        return user.ritual_intensity_score
    
    async def log_event(
        self, 
        user_id, 
        event_type: EventType, 
        ritual_phase: Optional[RitualPhase] = None,
        conversion: bool = False,
        metadata: Optional[dict] = None
    ) -> RitualEvent:
        """Log ritual event for analytics."""
        event = RitualEvent(
            user_id=user_id,
            event_type=event_type.value,
            ritual_phase=ritual_phase.value if ritual_phase else None,
            conversion_flag=conversion,
            metadata=metadata,
        )
        self.db.add(event)
        return event
    
    def get_week_message_type(self, user: User) -> str:
        """
        Determine which message type to send based on ritual phase.
        
        Returns: 'FULL_SANKALP', 'LIGHT_BLESSING', 'SILENT_WISDOM', 'MAHA_SANKALP', or 'SKIP'
        """
        phase = self.get_ritual_phase(user.ritual_cycle_day)
        
        if phase == RitualPhase.INITIATION:
            eligible, _ = self.is_eligible_for_sankalp(user)
            return "FULL_SANKALP" if eligible else "SKIP"
        
        elif phase == RitualPhase.BLESSING:
            return "LIGHT_BLESSING"
        
        elif phase == RitualPhase.SILENT:
            return "SILENT_WISDOM"
        
        elif phase == RitualPhase.MAHA:
            eligible, _ = self.is_eligible_for_sankalp(user)
            return "MAHA_SANKALP" if eligible else "SKIP"
        
        return "SKIP"
