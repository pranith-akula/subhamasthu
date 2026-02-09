"""RitualEvent model - tracks user ritual interactions for analytics."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RitualEvent(Base):
    """
    Analytics table for tracking ritual lifecycle events.
    
    Used to analyze:
    - Conversion rates per ritual phase
    - Fatigue signals (drops, blocks)
    - Time-to-payment patterns
    """
    
    __tablename__ = "ritual_events"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Event type: SANKALP_PROMPT, LIGHT_BLESSING, SILENT_WISDOM, MAHA_SANKALP, CONVERSION, etc.
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    
    # Ritual phase when event occurred
    ritual_phase: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    
    # Did this event lead to conversion?
    conversion_flag: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    # Additional metadata (JSON)
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    
    def __repr__(self) -> str:
        return f"<RitualEvent {self.event_type} user={self.user_id}>"
