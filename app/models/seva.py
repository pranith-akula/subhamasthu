"""Seva models - Annadanam ledger and batch transfers."""

import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, DateTime, Date, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SevaLedger(Base):
    """
    Seva ledger tracking platform fee vs seva amount per sankalp.
    Each paid sankalp creates one ledger entry.
    """
    
    __tablename__ = "seva_ledger"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Foreign key to sankalp (unique - one entry per sankalp)
    sankalp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sankalps.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    
    # Platform fee portion
    platform_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    
    # Seva (Annadanam) portion
    seva_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    
    # Batch ID (null until assigned to a batch)
    batch_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<SevaLedger sankalp={self.sankalp_id} seva={self.seva_amount}>"


class SevaBatch(Base):
    """
    Seva batch for periodic Annadanam transfers.
    Groups multiple ledger entries for batch transfer to NGO/temple.
    """
    
    __tablename__ = "seva_batches"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Unique batch identifier
    batch_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    
    # Period covered
    period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    
    period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    
    # Total seva amount in batch
    total_seva_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    
    # Transfer reference (bank ref, UPI ref, etc.)
    transfer_reference: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    
    # Transfer status
    transfer_status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<SevaBatch {self.batch_id} {self.transfer_status}>"
