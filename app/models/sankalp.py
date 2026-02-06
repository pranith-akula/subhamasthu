"""Sankalp model - tracks sankalp intent and payment status."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy import String, DateTime, ForeignKey, Numeric, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.fsm.states import SankalpCategory, SankalpTier, SankalpStatus


class Sankalp(Base):
    """
    Sankalp record tracking intent, payment, and closure.
    One sankalp per user per week (enforced by cooldown).
    """
    
    __tablename__ = "sankalps"
    
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
    
    # Category selected by user
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    # Deity for this sankalp
    deity: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Auspicious day when sankalp was made
    auspicious_day: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    
    # Pricing tier
    tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    
    # Payment amount
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    
    # Currency code
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )
    
    # Current status
    status: Mapped[str] = mapped_column(
        String(30),
        default=SankalpStatus.INITIATED.value,
        nullable=False,
    )
    
    # Razorpay payment link ID
    payment_link_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Razorpay reference data (JSON for flexibility)
    razorpay_ref: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    
    # Receipt URL (S3/R2 link)
    receipt_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # Temple where seva was performed (NEW - links to temples table)
    temple_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
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
        return f"<Sankalp {self.id} {self.category} {self.status}>"
    
    @property
    def is_paid(self) -> bool:
        """Check if sankalp is paid."""
        return self.status in [
            SankalpStatus.PAID.value,
            SankalpStatus.RECEIPT_SENT.value,
            SankalpStatus.CLOSED.value,
        ]
