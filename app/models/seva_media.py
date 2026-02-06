"""
Seva Media Model - Store footage for Annadanam proof.
Pooled footage model: Upload once, send to multiple donors.
"""

import uuid
from datetime import datetime, date, time
from typing import Optional
from enum import Enum

from sqlalchemy import Column, String, DateTime, Integer, Date, Time, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class MediaType(str, Enum):
    """Type of media file."""
    IMAGE = "image"
    VIDEO = "video"


# Fallback temple list for Hyderabad region
HYDERABAD_TEMPLES = [
    {"name": "ISKCON Temple", "location": "బంజారాహిల్స్, హైదరాబాద్"},
    {"name": "బిర్లా మందిరం", "location": "నోబెల్ నగర్, హైదరాబాద్"},
    {"name": "చిలుకూరు బాలాజీ", "location": "చిలుకూరు, హైదరాబాద్"},
    {"name": "జగన్నాధ ఆలయం", "location": "బంజారాహిల్స్, హైదరాబాద్"},
    {"name": "కీసరగుట్ట ఆలయం", "location": "కీసర, హైదరాబాద్"},
    {"name": "పెద్దమ్మ గుడి", "location": "జూబ్లీహిల్స్, హైదరాబాద్"},
    {"name": "సాయిబాబా మందిరం", "location": "అమీర్‌పేట, హైదరాబాద్"},
    {"name": "అష్టలక్ష్మి ఆలయం", "location": "బంజారాహిల్స్, హైదరాబాద్"},
    {"name": "ఎల్లమ్మ దేవాలయం", "location": "మహంకాళి, హైదరాబాద్"},
    {"name": "వేంకటేశ్వర ఆలయం", "location": "సికింద్రాబాద్, హైదరాబాద్"},
]


class SevaMedia(Base):
    """
    Seva media pool for Annadanam proof.
    
    Pooled model: Same footage can be sent to multiple donors.
    """
    __tablename__ = "seva_medias"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Media info
    media_type = Column(SQLEnum(MediaType, native_enum=False), nullable=False, default=MediaType.IMAGE)
    cloudinary_url = Column(String(500), nullable=False)
    cloudinary_public_id = Column(String(200), nullable=True)  # For deletion
    
    # Optional metadata (falls back to random Hyderabad temple if not provided)
    temple_name = Column(String(200), nullable=True)
    location = Column(String(200), nullable=True)
    
    # Seva info
    seva_date = Column(Date, nullable=True)  # If null, use "yesterday" when sending
    seva_time = Column(Time, nullable=True)  # If null, use 12:30 PM
    families_fed = Column(Integer, nullable=True)  # If null, use 50
    
    # Tracking
    used_count = Column(Integer, default=0)  # How many times sent
    caption = Column(Text, nullable=True)  # Optional custom caption
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def get_temple_info(self) -> dict:
        """Get temple info, fallback to random Hyderabad temple if not set."""
        import random
        
        if self.temple_name and self.location:
            return {"name": self.temple_name, "location": self.location}
        
        # Pick random temple from fallback list
        return random.choice(HYDERABAD_TEMPLES)
    
    def get_seva_time_display(self) -> str:
        """Get formatted seva time, default 12:30 PM."""
        if self.seva_time:
            return self.seva_time.strftime("%I:%M %p")
        return "12:30 PM"
    
    def get_families_fed(self) -> int:
        """Get families fed count, default 50."""
        return self.families_fed or 50
    
    def increment_usage(self):
        """Increment usage count."""
        self.used_count = (self.used_count or 0) + 1
