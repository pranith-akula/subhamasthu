"""
Seva Proof Service - Send Annadanam proof to donors.
Pooled footage model with scheduled 11am delivery.
"""

import logging
import random
from datetime import date, datetime, timedelta
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.seva_media import SevaMedia, MediaType, HYDERABAD_TEMPLES
from app.models.sankalp import Sankalp
from app.models.user import User
from app.services.gupshup_service import GupshupService

logger = logging.getLogger(__name__)


# Telugu month names
TELUGU_MONTHS = [
    "జనవరి", "ఫిబ్రవరి", "మార్చి", "ఏప్రిల్", "మే", "జూన్",
    "జూలై", "ఆగస్టు", "సెప్టెంబర్", "అక్టోబర్", "నవంబర్", "డిసెంబర్"
]


class SevaProofService:
    """Service for managing and sending Seva proof to donors."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gupshup = GupshupService()
    
    async def get_random_proof(self) -> Optional[SevaMedia]:
        """
        Get a random proof from the pool.
        Prefers least-used media for fair distribution.
        """
        # Get media with lowest usage count
        result = await self.db.execute(
            select(SevaMedia)
            .order_by(SevaMedia.used_count.asc(), func.random())
            .limit(1)
        )
        
        return result.scalar_one_or_none()
    
    async def get_proof_by_id(self, media_id) -> Optional[SevaMedia]:
        """Get specific proof by ID."""
        result = await self.db.execute(
            select(SevaMedia).where(SevaMedia.id == media_id)
        )
        return result.scalar_one_or_none()
    
    async def add_media(
        self,
        cloudinary_url: str,
        media_type: MediaType = MediaType.IMAGE,
        temple_name: Optional[str] = None,
        location: Optional[str] = None,
        seva_date: Optional[date] = None,
        families_fed: Optional[int] = None,
        caption: Optional[str] = None,
        cloudinary_public_id: Optional[str] = None,
    ) -> SevaMedia:
        """Add new media to the pool."""
        media = SevaMedia(
            cloudinary_url=cloudinary_url,
            media_type=media_type,
            temple_name=temple_name,
            location=location,
            seva_date=seva_date,
            families_fed=families_fed,
            caption=caption,
            cloudinary_public_id=cloudinary_public_id,
        )
        
        self.db.add(media)
        await self.db.commit()
        await self.db.refresh(media)
        
        logger.info(f"Added seva media: {media.id}")
        return media
    
    def _format_date_telugu(self, d: date) -> str:
        """Format date in Telugu style."""
        month = TELUGU_MONTHS[d.month - 1]
        return f"{d.day} {month} {d.year}"
    
    async def send_proof_to_donor(
        self,
        user: User,
        sankalp: Sankalp,
        media: Optional[SevaMedia] = None,
    ) -> bool:
        """
        Send seva proof to a specific donor.
        
        If no media specified, picks randomly from pool.
        """
        # Get random proof if not specified
        if not media:
            media = await self.get_random_proof()
        
        if not media:
            logger.warning("No seva media available in pool")
            return False
        
        # Get temple info
        temple_obj = None
        if media.temple_id:
            try:
                from app.models.temple import Temple
                result = await self.db.execute(select(Temple).where(Temple.id == media.temple_id))
                temple_obj = result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Failed to fetch temple {media.temple_id}: {e}")

        # Get temple info (fallback to random Hyderabad temple if no obj)
        temple_info = media.get_temple_info(temple_obj)
        
        # Seva date = payment date + 1 day (next morning)
        payment_date = sankalp.created_at.date() if sankalp.created_at else date.today()
        seva_display_date = payment_date + timedelta(days=1)
        
        # Format date in Telugu
        date_telugu = self._format_date_telugu(seva_display_date)
        
        # Seva time (default 12:30 PM)
        seva_time = media.get_seva_time_display()
        
        # Families fed
        families = media.get_families_fed()
        
        # Build caption
        caption = f"""🙏 మీ అన్నదాన సేవ పూర్తయింది!

📍 {temple_info['name']}
   {temple_info['location']}

📅 {date_telugu}, {seva_time}
🍲 {families} కుటుంబాలకు భోజనం అందించబడింది

మీ త్యాగానికి ధన్యవాదాలు 🙏

సర్వే జనాః సుఖినో భవంతు"""
        
        # Send media via WhatsApp
        if media.media_type == MediaType.VIDEO:
            msg_id = await self.gupshup.send_video_message(
                phone=user.phone,
                video_url=media.cloudinary_url,
                caption=caption,
            )
        else:
            msg_id = await self.gupshup.send_image_message(
                phone=user.phone,
                image_url=media.cloudinary_url,
                caption=caption,
            )
        
        if msg_id:
            # Increment usage count
            media.increment_usage()
            await self.db.commit()
            
            logger.info(f"Sent seva proof to {user.phone}")
            return True
        
        return False
    
    async def get_yesterday_donors(self) -> List[tuple]:
        """Get users who paid yesterday (need proof today at 11am)."""
        yesterday = date.today() - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday, datetime.min.time())
        yesterday_end = datetime.combine(yesterday, datetime.max.time())
        
        from app.fsm.states import SankalpStatus
        
        result = await self.db.execute(
            select(User, Sankalp)
            .join(Sankalp, Sankalp.user_id == User.id)
            .where(
                Sankalp.status == SankalpStatus.PAID,
                Sankalp.paid_at >= yesterday_start,
                Sankalp.paid_at <= yesterday_end,
            )
        )
        
        return result.all()
    
    async def send_proof_to_yesterday_donors(self) -> int:
        """
        Send proof to all donors from yesterday.
        Called by scheduled worker at 11am.
        """
        donors = await self.get_yesterday_donors()
        
        if not donors:
            logger.info("No donors from yesterday to send proof to")
            return 0
        
        sent = 0
        for user, sankalp in donors:
            try:
                success = await self.send_proof_to_donor(user, sankalp)
                if success:
                    sent += 1
            except Exception as e:
                logger.error(f"Failed to send proof to {user.phone}: {e}")
        
        logger.info(f"Sent seva proof to {sent}/{len(donors)} yesterday donors")
        return sent
    
    async def get_pool_stats(self) -> dict:
        """Get statistics about the media pool."""
        total = await self.db.execute(select(func.count(SevaMedia.id)))
        total_count = total.scalar() or 0
        
        images = await self.db.execute(
            select(func.count(SevaMedia.id))
            .where(SevaMedia.media_type == MediaType.IMAGE)
        )
        image_count = images.scalar() or 0
        
        videos = await self.db.execute(
            select(func.count(SevaMedia.id))
            .where(SevaMedia.media_type == MediaType.VIDEO)
        )
        video_count = videos.scalar() or 0
        
        return {
            "total": total_count,
            "images": image_count,
            "videos": video_count,
        }
