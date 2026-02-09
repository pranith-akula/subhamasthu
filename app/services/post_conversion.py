"""
Post-Conversion Engagement Chain.

Each paid Sankalp spawns 3 future touchpoints:
1. Day 0: Payment confirmation + Sankalp PDF
2. Day 3: Execution status update
3. Day 7: Impact photo + meal count

This increases perceived value per ask and creates anticipation.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sankalp import Sankalp, SankalpStatus
from app.models.user import User
from app.models.seva_execution import SevaExecution
from app.services.meta_whatsapp_service import MetaWhatsappService

logger = logging.getLogger(__name__)


class PostConversionService:
    """
    Manages the post-conversion engagement chain.
    
    Touch Schedule:
    - Day 0: Immediate confirmation + Sankalp PDF
    - Day 3: Execution status update
    - Day 7: Impact photo + meal count
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.whatsapp = MetaWhatsappService()
    
    async def send_day0_confirmation(self, user: User, sankalp: Sankalp) -> bool:
        """
        Day 0: Immediate payment confirmation with Sankalp details.
        
        Includes:
        - Sankalp Patram (formal statement)
        - Tier and amount
        - Expected execution timeline
        """
        name = user.name or "భక్తుడు"
        category = sankalp.category or "కుటుంబ క్షేమం"
        tier = sankalp.tier or "TIER_S30"
        
        # Map tier to families fed
        families_map = {
            "TIER_S15": "10",
            "TIER_S30": "25",
            "TIER_S50": "50",
        }
        families = families_map.get(tier, "25")
        
        # Calculate expected execution date (next Friday)
        today = datetime.now(ZoneInfo("Asia/Kolkata"))
        days_until_friday = (4 - today.weekday()) % 7
        if days_until_friday == 0:
            days_until_friday = 7
        execution_date = today + timedelta(days=days_until_friday)
        execution_date_str = execution_date.strftime("%d %B %Y")
        
        message = f"""🙏 {name}, మీ సంకల్పం స్వీకరించబడింది!

📜 సంకల్ప పత్రం:
ఈ రోజు {category} కోసం సంకల్పం చేయబడింది.
మీ త్యాగం ద్వారా {families} కుటుంబాలకు అన్నదానం జరుగుతుంది.

📅 నిర్ణీత తేదీ: {execution_date_str}

3 రోజుల్లో సేవా నవీకరణ అందించబడుతుంది.
7 రోజుల్లో అన్నదాన ఫోటో పంపబడుతుంది.

ధర్మం రక్షతి రక్షితః 🙏"""
        
        msg_id = await self.whatsapp.send_text_message(
            phone=user.phone,
            message=message,
        )
        
        if msg_id:
            # Update sankalp with next follow-up date
            sankalp.follow_up_day = 3
            sankalp.next_follow_up_at = datetime.now(ZoneInfo("UTC")) + timedelta(days=3)
        
        return msg_id is not None
    
    async def send_day3_status(self, user: User, sankalp: Sankalp) -> bool:
        """
        Day 3: Execution status update.
        
        Builds anticipation by showing progress.
        """
        name = user.name or "భక్తుడు"
        
        # Check if SevaExecution exists
        result = await self.db.execute(
            select(SevaExecution).where(SevaExecution.sankalp_id == sankalp.id)
        )
        seva = result.scalar_one_or_none()
        
        if seva and seva.status in ["executed", "verified"]:
            # Already executed
            meals = seva.meals_served or 25
            message = f"""🙏 {name}, శుభవార్త!

మీ సంకల్పం విజయవంతంగా నిర్వహించబడింది.

🍚 {meals} కుటుంబాలకు అన్నదానం పూర్తయింది!

4 రోజుల్లో ఫోటో రూపంలో ప్రసాదం పంపబడుతుంది.

ఓం శాంతి 🙏"""
        else:
            # Pending - show anticipation
            message = f"""🙏 {name}, మీ సంకల్పం తయారవుతోంది.

ఈ శుక్రవారం మీ పేరిట అన్నదానం జరుగుతుంది.

దేవాలయంలో మీ సంకల్పం స్వీకరించబడింది.
భక్తిపూర్వకంగా సేవ నిర్వహించబడుతుంది.

4 రోజుల్లో పూర్తయిన సేవా ఫోటో అందుతుంది.

ధర్మం రక్షతి రక్షితః 🙏"""
        
        msg_id = await self.whatsapp.send_text_message(
            phone=user.phone,
            message=message,
        )
        
        if msg_id:
            # Update next follow-up
            sankalp.follow_up_day = 7
            sankalp.next_follow_up_at = datetime.now(ZoneInfo("UTC")) + timedelta(days=4)
        
        return msg_id is not None
    
    async def send_day7_impact(self, user: User, sankalp: Sankalp) -> bool:
        """
        Day 7: Impact photo + meal count.
        
        Final touchpoint showing real impact.
        """
        name = user.name or "భక్తుడు"
        
        # Get SevaExecution for this sankalp
        result = await self.db.execute(
            select(SevaExecution).where(SevaExecution.sankalp_id == sankalp.id)
        )
        seva = result.scalar_one_or_none()
        
        if seva and seva.status == "verified" and seva.photo_url:
            # Has verified photo - send with image
            meals = seva.meals_served or 25
            message = f"""🙏 {name}, మీ సేవ పూర్తయింది!

🍚 {meals} కుటుంబాలకు అన్నదానం విజయవంతంగా జరిగింది.

ఇది మీ త్యాగం ద్వారా సాధ్యమైంది.

మీరు ఇప్పటివరకు {user.total_sankalps_count or 1} సంకల్పాలలో పాల్గొన్నారు.

"దాతృత్వం పరమో ధర్మః"
— మహాభారతం

ధర్మం రక్షతి రక్షితః 🙏"""
            
            # Try to send with image
            try:
                msg_id = await self.whatsapp.send_image_message(
                    phone=user.phone,
                    image_url=seva.photo_url,
                    caption=message,
                )
            except:
                # Fallback to text
                msg_id = await self.whatsapp.send_text_message(
                    phone=user.phone,
                    message=message,
                )
        else:
            # No photo yet - send text update
            meals = seva.meals_served if seva else 25
            message = f"""🙏 {name}, మీ సేవ పూర్తయింది!

🍚 {meals} కుటుంబాలకు అన్నదానం విజయవంతంగా జరిగింది.

మీరు ఇప్పటివరకు {user.total_sankalps_count or 1} సంకల్పాలలో పాల్గొన్నారు.

ధర్మం రక్షతి రక్షితః 🙏"""
            
            msg_id = await self.whatsapp.send_text_message(
                phone=user.phone,
                message=message,
            )
        
        if msg_id:
            # Mark chain complete
            sankalp.follow_up_day = 0
            sankalp.next_follow_up_at = None
        
        return msg_id is not None
    
    async def process_pending_follow_ups(self) -> int:
        """
        Process all pending follow-ups (called by worker).
        
        Returns count of messages sent.
        """
        now = datetime.now(ZoneInfo("UTC"))
        
        # Find sankalps with due follow-ups
        result = await self.db.execute(
            select(Sankalp).where(
                and_(
                    Sankalp.status == SankalpStatus.PAID.value,
                    Sankalp.next_follow_up_at <= now,
                    Sankalp.follow_up_day > 0,
                )
            )
        )
        sankalps = result.scalars().all()
        
        sent = 0
        for sankalp in sankalps:
            try:
                # Get user
                from app.services.user_service import UserService
                user_service = UserService(self.db)
                user = await user_service.get_user_by_id(sankalp.user_id)
                
                if not user:
                    continue
                
                if sankalp.follow_up_day == 3:
                    success = await self.send_day3_status(user, sankalp)
                elif sankalp.follow_up_day == 7:
                    success = await self.send_day7_impact(user, sankalp)
                else:
                    continue
                
                if success:
                    sent += 1
                    
            except Exception as e:
                logger.error(f"Failed to send follow-up for sankalp {sankalp.id}: {e}")
        
        await self.db.commit()
        logger.info(f"Processed {sent}/{len(sankalps)} follow-ups")
        return sent
