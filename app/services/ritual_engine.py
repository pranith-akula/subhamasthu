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


class SankalpIntensity(str, Enum):
    """
    Progressive sankalp intensity based on cycle and behavior.
    
    Cycle 1: GENTLE (Week 1), STRONG (Week 4)
    Cycle 2: MEDIUM (Week 1), MAHA (Week 4)
    Cycle 3+: LEADERSHIP (Week 1), COLLECTIVE (Week 4)
    Week 2: LIGHT (all cycles)
    Week 3: SILENT (all cycles)
    """
    GENTLE = "GENTLE"           # Cycle 1, Week 1 - Soft invitation
    STRONG = "STRONG"           # Cycle 1, Week 4 - Clear value proposition
    MEDIUM = "MEDIUM"           # Cycle 2, Week 1 - Deeper connection
    MAHA = "MAHA"               # Cycle 2, Week 4 - Elevated collective
    LEADERSHIP = "LEADERSHIP"   # Cycle 3+, Week 1 - Core circle framing
    COLLECTIVE = "COLLECTIVE"   # Cycle 3+, Week 4 - Anchoring community
    LIGHT = "LIGHT"             # Week 2 (all cycles) - Light blessing
    SILENT = "SILENT"           # Week 3 (all cycles) - Wisdom, no ask


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
    def is_in_cooldown(user: User) -> bool:
        """Check if user is in 168-hour (7-day) cooldown from last paid Sankalp."""
        if not user.last_sankalp_at:
            return False
        
        hours_since = (datetime.now(ZoneInfo("UTC")) - user.last_sankalp_at).total_seconds() / 3600
        return hours_since < 168  # 7 days
    
    @staticmethod
    def increment_cycle_day(user: User) -> int:
        """
        Increment ritual cycle day (1-28, wraps around).
        Also updates ritual_phase based on new day.
        
        CRITICAL: Increments devotional_cycle_number on wrap-around (28→1)
        but CAPS at 4 to prevent infinite growth.
        
        Returns: New cycle day
        """
        new_day = user.ritual_cycle_day + 1
        if new_day > 28:
            new_day = 1
            # INCREMENT DEVOTIONAL CYCLE (capped at 4)
            current_cycle = user.devotional_cycle_number or 1
            if current_cycle < 4:
                user.devotional_cycle_number = current_cycle + 1
        
        user.ritual_cycle_day = new_day
        user.ritual_phase = RitualOrchestrator.get_ritual_phase(new_day).value
        
        return new_day
    
    def get_sankalp_intensity(self, user: User) -> SankalpIntensity:
        """
        Get sankalp message intensity based on:
        1. Devotional cycle (1-4)
        2. Ritual week (1-4)
        3. Behavior (has paid before?)
        4. Cooldown status
        
        This is the core progressive messaging logic.
        """
        week = self.get_ritual_week(user.ritual_cycle_day)
        cycle = user.devotional_cycle_number or 1
        has_paid = (user.total_sankalps_count or 0) > 0
        
        # Week 2 & 3 are always the same - no ask
        if week == 2:
            return SankalpIntensity.LIGHT
        elif week == 3:
            return SankalpIntensity.SILENT
        
        # If in cooldown, downgrade to LIGHT (never send strong ask if blocked)
        if self.is_in_cooldown(user):
            return SankalpIntensity.LIGHT
        
        # Week 1 & 4 depend on cycle and behavior
        base_intensity = self._get_base_intensity(cycle, week)
        
        # BEHAVIOR MODIFIER: Downgrade intensity if user never converted
        if not has_paid:
            base_intensity = self._downgrade_intensity(base_intensity)
        
        return base_intensity
    
    def _get_base_intensity(self, cycle: int, week: int) -> SankalpIntensity:
        """Get base intensity from cycle and week matrix."""
        if week == 1:
            if cycle == 1:
                return SankalpIntensity.GENTLE
            elif cycle == 2:
                return SankalpIntensity.MEDIUM
            else:  # cycle >= 3
                return SankalpIntensity.LEADERSHIP
        else:  # week == 4
            if cycle == 1:
                return SankalpIntensity.STRONG
            elif cycle == 2:
                return SankalpIntensity.MAHA
            else:  # cycle >= 3
                return SankalpIntensity.COLLECTIVE
    
    def _downgrade_intensity(self, intensity: SankalpIntensity) -> SankalpIntensity:
        """
        Downgrade intensity by one level if user has never paid.
        
        Never call someone "core devotee" if they've never converted.
        """
        downgrade_map = {
            SankalpIntensity.LEADERSHIP: SankalpIntensity.MEDIUM,
            SankalpIntensity.COLLECTIVE: SankalpIntensity.MAHA,
            SankalpIntensity.MEDIUM: SankalpIntensity.GENTLE,
            SankalpIntensity.MAHA: SankalpIntensity.STRONG,
            SankalpIntensity.STRONG: SankalpIntensity.GENTLE,
            SankalpIntensity.GENTLE: SankalpIntensity.GENTLE,  # No further downgrade
        }
        return downgrade_map.get(intensity, intensity)
    
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
