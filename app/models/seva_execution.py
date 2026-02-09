"""SevaExecution model - tracks actual meals served per Sankalp."""

import uuid
from datetime import datetime
from typing import Optional
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SevaExecutionStatus(str, Enum):
    """Status of seva execution."""
    PENDING = "pending"      # Sankalp paid, awaiting execution
    EXECUTED = "executed"    # Meals served, awaiting verification
    VERIFIED = "verified"    # Photo uploaded, admin verified


class SevaExecution(Base):
    """
    Tracks actual seva execution for impact transparency.
    
    Flow:
    1. Sankalp paid → SevaExecution created (status=pending)
    2. Temple serves meals → status=executed, meals_served filled
    3. Admin uploads photo → status=verified, photo_url filled
    
    Impact aggregation ONLY counts verified records.
    """
    
    __tablename__ = "seva_executions"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Link to paid Sankalp
    sankalp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sankalps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Temple where execution happened
    temple_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("temples.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Actual meals served (may differ from tier)
    meals_served: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    
    # Status tracking - use PostgreSQL ENUM type
    status: Mapped[str] = mapped_column(
        ENUM('pending', 'executed', 'verified', name='seva_execution_status', create_type=False),
        nullable=False,
        default='pending',
    )
    
    # Execution timestamp
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Verification timestamp
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Proof photo URL (S3/R2)
    photo_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Admin who verified
    verified_by: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    # Logistics notes
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Future: Batch processing for scale
    batch_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
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
        return f"<SevaExecution {self.id} meals={self.meals_served} status={self.status}>"
    
    @property
    def is_verified(self) -> bool:
        """Check if execution is verified (counts toward impact)."""
        return self.status == SevaExecutionStatus.VERIFIED.value
