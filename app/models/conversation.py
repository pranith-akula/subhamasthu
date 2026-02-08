"""Conversation model - tracks conversation state and context."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.fsm.states import ConversationState


class Conversation(Base):
    """
    Conversation table tracking FSM state and context.
    Stores selected category, tier, pending sankalp ID, etc.
    """
    
    __tablename__ = "conversations"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Foreign key to user
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Current FSM state
    state: Mapped[str] = mapped_column(
        String(50),
        default=ConversationState.NEW.value,
        nullable=False,
    )
    
    # Context JSON for flow-specific data
    # e.g., {"selected_category": "CAT_FAMILY", "selected_tier": "TIER_S30", "pending_sankalp_id": "uuid"}
    context: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    
    # Last inbound message ID (for idempotency)
    last_inbound_msg_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Last outbound message ID
    last_outbound_msg_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<Conversation {self.id} state={self.state}>"
    
    def set_context(self, key: str, value: Any) -> None:
        """Set a context value."""
        # Create a copy to trigger SQLAlchemy change detection on JSON field
        if self.context is None:
            ctx = {}
        else:
            ctx = dict(self.context)
            
        ctx[key] = value
        self.context = ctx
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """Get a context value."""
        if self.context is None:
            return default
        return self.context.get(key, default)
    
    def clear_context(self) -> None:
        """Clear all context."""
        self.context = {}
