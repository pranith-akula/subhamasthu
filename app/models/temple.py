"""
Temple Model - Store temple metadata for seva attribution.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Temple(Base):
    """
    Temple database for Annadanam seva locations.
    
    Used for:
    - Attributing SevaMedia to specific temples
    - Enhancing proof messages with real temple names
    - Tracking which temples are active partners
    """
    __tablename__ = "temples"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Temple info
    name = Column(String(200), nullable=False)
    name_telugu = Column(String(200), nullable=True)
    location = Column(String(200), nullable=True)
    city = Column(String(100), default="Hyderabad")
    
    # Religious info
    deity = Column(String(100), nullable=True)
    
    # Media
    photo_url = Column(String(500), nullable=True)
    google_maps_url = Column(String(500), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Temple {self.name} ({self.city})>"
    
    @property
    def display_name(self) -> str:
        """Get display name, preferring Telugu if available."""
        return self.name_telugu or self.name
    
    @property
    def full_location(self) -> str:
        """Get full location string."""
        if self.location and self.city:
            return f"{self.location}, {self.city}"
        return self.city or self.location or "Hyderabad"
