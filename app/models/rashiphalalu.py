"""Rashiphalalu cache model - daily horoscope content cache."""

import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, DateTime, Date, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RashiphalaluCache(Base):
    """
    Cache for daily Rashiphalalu messages.
    Pre-generated via OpenAI, one per rashi per day per language variant.
    Unique constraint on (date, rashi, language_variant).
    """
    
    __tablename__ = "rashiphalalu_cache"
    
    __table_args__ = (
        UniqueConstraint(
            "date", "rashi", "language_variant",
            name="uq_rashiphalalu_date_rashi_lang"
        ),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Date for this horoscope
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    
    # Rashi (zodiac sign)
    rashi: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    
    # Language variant (e.g., "te_en" for Telugu-English mix)
    language_variant: Mapped[str] = mapped_column(
        String(10),
        default="te_en",
        nullable=False,
    )
    
    # The actual message content
    message_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    # Model used for generation
    model: Mapped[str] = mapped_column(
        String(50),
        default="gpt-4o-mini",
        nullable=False,
    )
    
    # Prompt template version (for auditing)
    prompt_version: Mapped[str] = mapped_column(
        String(20),
        default="v1",
        nullable=False,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    def __repr__(self) -> str:
        return f"<RashiphalaluCache {self.date} {self.rashi}>"
