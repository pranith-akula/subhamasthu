"""
Receipt Service - Telugu PDF receipt generation.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.sankalp import Sankalp
from app.fsm.states import SankalpCategory, SankalpTier
from app.services.gupshup_service import GupshupService

logger = logging.getLogger(__name__)


# Telugu mappings
DEITY_TELUGU = {
    "venkateshwara": "వేంకటేశ్వర స్వామి",
    "shiva": "శివుడు",
    "vishnu": "విష్ణువు",
    "hanuman": "హనుమంతుడు",
    "durga": "దుర్గామాత",
    "lakshmi": "లక్ష్మీదేవి",
    "ganesha": "గణేషుడు",
    "saraswati": "సరస్వతీదేవి",
    "rama": "శ్రీరాముడు",
    "krishna": "శ్రీకృష్ణుడు",
    "saibaba": "సాయిబాబా",
    "ayyappa": "అయ్యప్ప",
    "subrahmanya": "సుబ్రహ్మణ్యస్వామి",
    "other": "భగవంతుడు",
}

CATEGORY_TELUGU = {
    "family": "పిల్లలు / పరివారం",
    "health": "ఆరోగ్యం / రక్ష",
    "career": "ఉద్యోగం / ఆర్థికం",
    "peace": "మానసిక శాంతి",
}

DAY_TELUGU = {
    "sunday": "ఆదివారం",
    "monday": "సోమవారం",
    "tuesday": "మంగళవారం",
    "wednesday": "బుధవారం",
    "thursday": "గురువారం",
    "friday": "శుక్రవారం",
    "saturday": "శనివారం",
}

TIER_TELUGU = {
    "S15": ("సాముహిక త్యాగం", 10),
    "S30": ("విశేష త్యాగం", 25),
    "S50": ("ప్రత్యేక త్యాగం", 50),
}

MONTH_TELUGU = {
    1: "జనవరి", 2: "ఫిబ్రవరి", 3: "మార్చి", 4: "ఏప్రిల్",
    5: "మే", 6: "జూన్", 7: "జూలై", 8: "ఆగస్టు",
    9: "సెప్టెంబర్", 10: "అక్టోబర్", 11: "నవంబర్", 12: "డిసెంబర్",
}


class ReceiptService:
    """Service for generating and sending Telugu PDF receipts."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gupshup = GupshupService()
    
    async def generate_and_send_receipt(
        self,
        user: User,
        sankalp: Sankalp,
    ) -> Optional[str]:
        """
        Generate Telugu receipt and send to user.
        
        Returns the receipt URL on success.
        """
        try:
            # Generate Telugu receipt
            receipt_text = self._generate_telugu_receipt(user, sankalp)
            
            # Send receipt message
            msg_id = await self.gupshup.send_text_message(
                phone=user.phone,
                message=receipt_text,
            )
            
            if msg_id:
                logger.info(f"Telugu receipt sent for sankalp {sankalp.id}")
                return f"receipt://{sankalp.id}"
            
            return None
            
        except Exception as e:
            logger.error(f"Receipt generation failed: {e}", exc_info=True)
            return None
    
    def _generate_telugu_receipt(self, user: User, sankalp: Sankalp) -> str:
        """Generate Pure Telugu receipt message."""
        # Get Telugu names
        deity = DEITY_TELUGU.get(sankalp.deity, "భగవంతుడు")
        category = CATEGORY_TELUGU.get(sankalp.category, sankalp.category)
        day = DAY_TELUGU.get(sankalp.auspicious_day, sankalp.auspicious_day or "-")
        
        # Get tier info
        tier_info = TIER_TELUGU.get(sankalp.tier, ("త్యాగం", 10))
        tier_name = tier_info[0]
        families = tier_info[1]
        
        # Format date in Telugu
        date_telugu = self._format_date_telugu(sankalp.created_at)
        
        # Reference ID (short)
        ref_id = str(sankalp.id)[:8].upper()
        
        # User name
        name = user.name or "భక్తులు"
        
        return f"""📜 సంకల్ప సేవా రసీదు

━━━━━━━━━━━━━━━━━━━━━━
🙏 శుభమస్తు
━━━━━━━━━━━━━━━━━━━━━━

👤 పేరు: {name}
📅 తేది: {date_telugu}
🔢 రిఫరెన్స్: #{ref_id}

━━ సంకల్ప వివరాలు ━━

🙏 చింత: {category}
🙏 దేవత: {deity}
📆 శుభ దినం: {day}

━━ త్యాగ వివరాలు ━━

💰 త్యాగం: ${sankalp.amount} ({tier_name})
🍚 అన్నదానం: {families} కుటుంబాలకు

━━━━━━━━━━━━━━━━━━━━━━

✨ మీ సంకల్పం + త్యాగం పూర్తి అయింది ✨

ఈ త్యాగం ద్వారా అవసరమైన
కుటుంబాలకు అన్నదాన సేవ జరుగుతుంది.

━━━━━━━━━━━━━━━━━━━━━━

🙏 సర్వే జనాః సుఖినో భవంతు 🙏

ఓం శాంతి శాంతి శాంతిః"""
    
    def _format_date_telugu(self, dt: datetime) -> str:
        """Format datetime in Telugu."""
        month = MONTH_TELUGU.get(dt.month, str(dt.month))
        return f"{dt.day} {month} {dt.year}"
    
    def _get_families_fed(self, tier: str) -> int:
        """Get number of families fed based on tier."""
        tier_info = TIER_TELUGU.get(tier, ("", 10))
        return tier_info[1]
