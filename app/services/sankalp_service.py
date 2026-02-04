"""
Sankalp Service - Weekly sankalp flow management.
"""

import uuid
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import razorpay

from app.config import settings
from app.models.user import User
from app.models.sankalp import Sankalp
from app.fsm.states import SankalpCategory, SankalpTier, SankalpStatus, AuspiciousDay
from app.services.gupshup_service import GupshupService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


class SankalpService:
    """Service for managing weekly sankalp flow."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gupshup = GupshupService()
        self.razorpay = razorpay.Client(
            auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
        )
    
    async def send_weekly_prompts(self) -> int:
        """
        Send weekly reflection prompts to eligible users.
        Users are eligible if:
        - Their auspicious_day matches today
        - They are not in cooldown (last sankalp > 7 days ago)
        - They are in DAILY_PASSIVE or ONBOARDED state
        """
        today = datetime.now().strftime("%A").upper()
        
        user_service = UserService(self.db)
        eligible_users = await user_service.get_users_for_weekly_prompt(today)
        
        sent = 0
        for user in eligible_users:
            try:
                await self.send_reflection_prompt(user)
                sent += 1
            except Exception as e:
                logger.error(f"Failed to send prompt to {user.phone}: {e}")
        
        logger.info(f"Sent weekly prompts to {sent} users")
        return sent
    
    async def send_reflection_prompt(self, user: User) -> bool:
        """Send the weekly reflection prompt to a user."""
        deity_name = user.preferred_deity or "దేవుడు"
        
        message = f"""🙏 Shubhodayam {user.name or 'ji'},

Ee roju {user.auspicious_day or 'special'} day — {deity_name} krupa meeda undi.

Mee manasulo emi chinta undi? Oka nimisham aagandi, mee bhavanni share cheyandi.

Mee sankalp ni dharmam lo marchukodaniki idi oka avasaram."""
        
        buttons = [
            {"id": SankalpCategory.FAMILY.value, "title": "పిల్లలు/పరివారం"},
            {"id": SankalpCategory.HEALTH.value, "title": "ఆరోగ్యం/రక్ష"},
            {"id": SankalpCategory.CAREER.value, "title": "ఉద్యోగం/ఆర్థికం"},
        ]
        
        # Send with buttons (max 3, so Peace will be in a follow-up)
        msg_id = await self.gupshup.send_button_message(
            phone=user.phone,
            body_text=message,
            buttons=buttons,
        )
        
        if msg_id:
            from app.fsm.states import ConversationState
            user_service = UserService(self.db)
            await user_service.update_user_state(user, ConversationState.WAITING_FOR_CATEGORY)
            return True
        
        return False
    
    async def create_sankalp(
        self,
        user: User,
        category: SankalpCategory,
        tier: SankalpTier,
    ) -> Sankalp:
        """Create a new sankalp record."""
        amount = Decimal(tier.amount_usd) / 100  # Convert cents to dollars
        
        sankalp = Sankalp(
            user_id=user.id,
            category=category.value,
            deity=user.preferred_deity,
            auspicious_day=user.auspicious_day,
            tier=tier.value,
            amount=amount,
            currency="USD",
            status=SankalpStatus.INITIATED.value,
        )
        
        self.db.add(sankalp)
        await self.db.flush()
        
        logger.info(f"Created sankalp {sankalp.id} for user {user.phone}")
        return sankalp
    
    async def create_payment_link(self, sankalp: Sankalp, user: User) -> str:
        """Create Razorpay payment link for the sankalp."""
        amount_paise = int(sankalp.amount * 100)  # Convert to paise
        
        try:
            payment_link = self.razorpay.payment_link.create({
                "amount": amount_paise,
                "currency": sankalp.currency,
                "accept_partial": False,
                "description": f"Sankalp Seva - {sankalp.category}",
                "customer": {
                    "contact": user.phone,
                    "name": user.name or "Devotee",
                },
                "notify": {
                    "sms": False,
                    "email": False,  # We handle notification via WhatsApp
                },
                "notes": {
                    "sankalp_id": str(sankalp.id),
                    "user_id": str(user.id),
                    "category": sankalp.category,
                },
                "callback_url": "",  # Will use webhook instead
                "callback_method": "get",
            })
            
            # Update sankalp with payment link info
            sankalp.payment_link_id = payment_link["id"]
            sankalp.status = SankalpStatus.PAYMENT_PENDING.value
            sankalp.razorpay_ref = {
                "payment_link_id": payment_link["id"],
                "short_url": payment_link["short_url"],
            }
            
            logger.info(f"Created payment link {payment_link['id']} for sankalp {sankalp.id}")
            return payment_link["short_url"]
            
        except Exception as e:
            logger.error(f"Failed to create payment link: {e}")
            raise
    
    async def send_payment_link(self, user: User, sankalp: Sankalp, payment_url: str) -> bool:
        """Send payment link to user via WhatsApp."""
        category_display = SankalpCategory(sankalp.category).display_name_telugu
        tier_display = SankalpTier(sankalp.tier).display_name
        
        message = f"""🙏 Mee Sankalp Details:

📿 Category: {category_display}
🙏 Deity: {sankalp.deity or 'దేవుడు'}
💰 Seva: {tier_display}

Mee sankalp + Annadanam seva kosam ee link press cheyandi:
{payment_url}

Mee tyagam tho oka manchi pani jarigindi. 🙏"""
        
        msg_id = await self.gupshup.send_text_message(
            phone=user.phone,
            message=message,
        )
        
        if msg_id:
            from app.fsm.states import ConversationState
            user_service = UserService(self.db)
            await user_service.update_user_state(user, ConversationState.PAYMENT_LINK_SENT)
            return True
        
        return False
    
    async def send_tier_selection(self, user: User, category: SankalpCategory) -> bool:
        """Send tier selection buttons after category is selected."""
        deity_name = user.preferred_deity or "దేవుడు"
        
        message = f"""🙏 Mee sankalp: {category.display_name_telugu}

{deity_name} krupa tho, mee chinta ni Annadanam seva ga marchandi.

Mee seva tier select cheyandi:"""
        
        buttons = [
            {"id": SankalpTier.S15.value, "title": "$15 Samuhik"},
            {"id": SankalpTier.S30.value, "title": "$30 Vishesh"},
            {"id": SankalpTier.S50.value, "title": "$50 Parivaar"},
        ]
        
        msg_id = await self.gupshup.send_button_message(
            phone=user.phone,
            body_text=message,
            buttons=buttons,
            footer="Annadanam seva for 10/25/50 families",
        )
        
        if msg_id:
            from app.fsm.states import ConversationState
            user_service = UserService(self.db)
            await user_service.update_user_state(user, ConversationState.WAITING_FOR_TIER)
            return True
        
        return False
    
    async def send_closure_message(self, user: User, sankalp: Sankalp) -> bool:
        """Send closure message after successful payment."""
        message = f"""🙏✨ Mee sankalp + tyagam poorthi ayyayi. ✨🙏

{user.name or 'Ji'}, mee {SankalpCategory(sankalp.category).display_name_telugu} sankalp {sankalp.deity or 'దేవుడు'} daya tho record ayyindi.

Mee ${sankalp.amount} seva tho {self._get_families_fed(sankalp.tier)} families ki Annadanam jarigindi.

Mee tyagam meeku shanti, samruddhi teesthundi. 🙏

Mee receipt tavaralo vastundi."""
        
        msg_id = await self.gupshup.send_text_message(
            phone=user.phone,
            message=message,
        )
        
        return msg_id is not None
    
    async def get_sankalp_by_id(self, sankalp_id: uuid.UUID) -> Optional[Sankalp]:
        """Get sankalp by ID."""
        result = await self.db.execute(
            select(Sankalp).where(Sankalp.id == sankalp_id)
        )
        return result.scalar_one_or_none()
    
    def _get_families_fed(self, tier: str) -> int:
        """Get number of families fed based on tier."""
        mapping = {
            SankalpTier.S15.value: 10,
            SankalpTier.S30.value: 25,
            SankalpTier.S50.value: 50,
        }
        return mapping.get(tier, 10)
