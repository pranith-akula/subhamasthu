
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, Enum as SqEnum, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base
import enum

class MessageType(str, enum.Enum):
    RASHI = "RASHI"
    NURTURE = "NURTURE"
    SANKALP_INVITE = "SANKALP_INVITE" 
    ONBOARDING = "ONBOARDING"
    OTHER = "OTHER"

class MessageStatus(str, enum.Enum):
    SENT = "SENT"
    FAILED = "FAILED"
    DELIVERED = "DELIVERED"
    READ = "READ"

class MessageLog(Base):
    __tablename__ = "message_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    message_type: Mapped[MessageType] = mapped_column(SqEnum(MessageType), nullable=False)
    content_preview: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[MessageStatus] = mapped_column(SqEnum(MessageStatus), default=MessageStatus.SENT)
    
    # Idempotency Key: essential for "Hourly Worker" to not double send
    # Format: "nurture_YYYY-MM-DD_user_uuid"
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="message_logs")
