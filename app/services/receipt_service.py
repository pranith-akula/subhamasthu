"""
Receipt Service - PDF receipt generation.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from jinja2 import Environment, FileSystemLoader

from app.models.user import User
from app.models.sankalp import Sankalp
from app.fsm.states import SankalpCategory, SankalpTier
from app.services.gupshup_service import GupshupService

logger = logging.getLogger(__name__)


class ReceiptService:
    """Service for generating and sending PDF receipts."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gupshup = GupshupService()
    
    async def generate_and_send_receipt(
        self,
        user: User,
        sankalp: Sankalp,
    ) -> Optional[str]:
        """
        Generate PDF receipt and send to user.
        
        Returns the receipt URL on success.
        """
        try:
            # Generate receipt HTML
            html_content = self._render_receipt_html(user, sankalp)
            
            # For v1, we'll skip PDF generation and just send a text receipt
            # In production, use WeasyPrint to generate PDF and upload to R2/S3
            receipt_text = self._generate_text_receipt(user, sankalp)
            
            # Send receipt message
            msg_id = await self.gupshup.send_text_message(
                phone=user.phone,
                message=receipt_text,
            )
            
            if msg_id:
                logger.info(f"Receipt sent for sankalp {sankalp.id}")
                # In production, return actual PDF URL
                return f"receipt://{sankalp.id}"
            
            return None
            
        except Exception as e:
            logger.error(f"Receipt generation failed: {e}", exc_info=True)
            return None
    
    def _render_receipt_html(self, user: User, sankalp: Sankalp) -> str:
        """Render receipt HTML from template."""
        # For now, return a simple HTML structure
        # In production, use Jinja2 template
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Sankalp Receipt</title>
    <style>
        body {{ font-family: 'Noto Sans Telugu', sans-serif; padding: 40px; }}
        .header {{ text-align: center; border-bottom: 2px solid #ff9933; }}
        .content {{ margin: 20px 0; }}
        .footer {{ text-align: center; color: #666; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🙏 Subhamasthu</h1>
        <p>Sankalp Seva Receipt</p>
    </div>
    <div class="content">
        <p><strong>Name:</strong> {user.name or 'Devotee'}</p>
        <p><strong>Date:</strong> {sankalp.created_at.strftime('%B %d, %Y')}</p>
        <p><strong>Category:</strong> {SankalpCategory(sankalp.category).display_name_telugu}</p>
        <p><strong>Deity:</strong> {sankalp.deity or 'దేవుడు'}</p>
        <p><strong>Amount:</strong> ${sankalp.amount} ({SankalpTier(sankalp.tier).display_name})</p>
        <p><strong>Ref:</strong> {str(sankalp.id)[:8].upper()}</p>
    </div>
    <div class="footer">
        <p>Mee sankalp + tyagam poorthi ayyayi. 🙏</p>
        <p>This is a receipt for your Annadanam Seva contribution.</p>
    </div>
</body>
</html>
"""
    
    def _generate_text_receipt(self, user: User, sankalp: Sankalp) -> str:
        """Generate a text receipt message."""
        category_name = SankalpCategory(sankalp.category).display_name_telugu
        tier_name = SankalpTier(sankalp.tier).display_name
        ref_id = str(sankalp.id)[:8].upper()
        
        return f"""📜 SANKALP SEVA RECEIPT

━━━━━━━━━━━━━━━━━━━━━━
🙏 Subhamasthu
━━━━━━━━━━━━━━━━━━━━━━

Name: {user.name or 'Devotee'}
Date: {sankalp.created_at.strftime('%B %d, %Y')}
Reference: #{ref_id}

━━ Sankalp Details ━━
Category: {category_name}
Deity: {sankalp.deity or 'దేవుడు'}
Auspicious Day: {sankalp.auspicious_day or '-'}

━━ Seva Details ━━
Tier: {tier_name}
Amount: ${sankalp.amount}
Annadanam: {self._get_families_fed(sankalp.tier)} families

━━━━━━━━━━━━━━━━━━━━━━
✨ Mee sankalp + tyagam poorthi ayyayi ✨

This contribution supports Annadanam 
seva for families in need.

🙏 Sarve Janah Sukhino Bhavantu 🙏
━━━━━━━━━━━━━━━━━━━━━━"""
    
    def _get_families_fed(self, tier: str) -> int:
        """Get number of families fed based on tier."""
        mapping = {
            SankalpTier.S15.value: 10,
            SankalpTier.S30.value: 25,
            SankalpTier.S50.value: 50,
        }
        return mapping.get(tier, 10)
