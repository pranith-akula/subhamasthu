"""Payment model - Razorpay payment records for idempotency."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Payment(Base):
    """
    Payment record for Razorpay webhook idempotency.
    razorpay_event_id is unique to prevent duplicate processing.
    """
    
    __tablename__ = "payments"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Foreign key to sankalp
    sankalp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sankalps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Razorpay payment ID
    razorpay_payment_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    
    # Razorpay event ID (unique for idempotency)
    razorpay_event_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    
    # Signature verification status
    signature_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
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
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<Payment {self.razorpay_payment_id}>"
