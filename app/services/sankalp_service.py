"""
Sankalp Service - Ritual-driven weekly Sankalp flow.

Psychological Arc:
చింత → సంకల్పం → పరిహారం → త్యాగం → పుణ్యం → శాంతి
"""

import uuid
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
import random

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


# Pariharam (ritual) options for each category
PARIHARAM_OPTIONS = {
    SankalpCategory.FAMILY.value: [
        "11 సార్లు 'ఓం నమో నారాయణాయ' జపం చేయండి",
        "కుటుంబంతో కలిసి ఒక భోజనం చేయండి",
        "ఒక వృద్ధుడిని/వృద్ధురాలిని ఆశీర్వదం తీసుకోండి",
    ],
    SankalpCategory.HEALTH.value: [
        "ఉదయం 11 సార్లు 'ఓం హ్రీం హనుమతే నమః' జపం చేయండి",
        "3 రోజులు తీపి మానండి",
        "5 నిమిషాలు మౌనంగా ధ్యానం చేయండి",
    ],
    SankalpCategory.CAREER.value: [
        "11 సార్లు గణేష మంత్రం జపించండి",
        "ఒక రోజు తెల్లవారుజామున లేచి సూర్యోదయం చూడండి",
        "పేద విద్యార్థికి ఏదైనా సహాయం చేయండి",
    ],
    SankalpCategory.PEACE.value: [
        "5 నిమిషాలు మౌన ధ్యానం చేయండి",
        "దీపం వెలిగించి ప్రార్థన చేయండి",
        "పక్షులకు గింజలు వేయండి",
    ],
}

# Deity to Telugu name mapping
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
}

# Day to Telugu name mapping
DAY_TELUGU = {
    "sunday": "ఆదివారం",
    "monday": "సోమవారం",
    "tuesday": "మంగళవారం",
    "wednesday": "బుధవారం",
    "thursday": "గురువారం",
    "friday": "శుక్రవారం",
    "saturday": "శనివారం",
}


class SankalpService:
    """
    Service for managing ritual-driven Sankalp flow.
    
    Flow:
    1. చింత (Chinta) - Problem selection
    2. సంకల్పం (Sankalp) - Formal framing
    3. పరిహారం (Pariharam) - Ritual action
    4. త్యాగం (Tyagam) - Monetary offering
    5. పుణ్యం (Punya) - Confirmation
    6. శాంతి (Shanti) - 7-day silence
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gupshup = GupshupService()
        if settings.razorpay_key_id and settings.razorpay_key_secret:
            self.razorpay = razorpay.Client(
                auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
            )
        else:
            self.razorpay = None
    
    async def send_weekly_prompts(self) -> int:
        """
        Send weekly reflection prompts to eligible users.
        
        Eligibility:
        - auspicious_day matches today
        - rashiphalalu_days_sent >= 6
        - Not in cooldown (last_sankalp_at > 7 days ago)
        - In DAILY_PASSIVE state
        """
        today = datetime.now().strftime("%A").upper()
        
        user_service = UserService(self.db)
        all_users = await user_service.get_users_for_weekly_prompt(today)
        
        # Filter by 6-day eligibility
        eligible_users = [u for u in all_users if u.is_eligible_for_sankalp]
        
        sent = 0
        for user in eligible_users:
            try:
                await self.send_chinta_prompt(user)
                sent += 1
            except Exception as e:
                logger.error(f"Failed to send prompt to {user.phone}: {e}")
        
        logger.info(f"Sent weekly prompts to {sent}/{len(all_users)} eligible users")
        return sent
    
    async def send_chinta_prompt(self, user: User) -> bool:
        """
        Step 1: చింత (Chinta) - Problem selection.
        Ask user to identify their worry/concern.
        
        NOW GPT-PERSONALIZED based on user's Rashi, Deity, and Panchang.
        """
        from app.services.personalization_service import PersonalizationService
        
        # Generate personalized Chinta prompt via GPT
        personalization = PersonalizationService(self.db)
        message = await personalization.generate_chinta_prompt(user)
        
        # Add instruction
        message += "\n\nఏ విషయంలో ఆందోళన ఉంది?"
        
        buttons = [
            {"id": SankalpCategory.FAMILY.value, "title": "👨‍👩‍👧 పిల్లలు/పరివారం"},
            {"id": SankalpCategory.HEALTH.value, "title": "💪 ఆరోగ్యం/రక్ష"},
            {"id": SankalpCategory.CAREER.value, "title": "💼 ఉద్యోగం/ఆర్థికం"},
        ]
        
        msg_id = await self.gupshup.send_button_message(
            phone=user.phone,
            body_text=message,
            buttons=buttons,
        )
        
        # Send second set for Peace category
        buttons2 = [
            {"id": SankalpCategory.PEACE.value, "title": "🧘 మానసిక శాంతి"},
        ]
        
        await self.gupshup.send_button_message(
            phone=user.phone,
            body_text="మరిన్ని ఎంపికలు:",
            buttons=buttons2,
        )
        
        if msg_id:
            from app.fsm.states import ConversationState
            user_service = UserService(self.db)
            await user_service.update_user_state(user, ConversationState.WAITING_FOR_CATEGORY)
            return True
        
        return False
    
    async def frame_sankalp(self, user: User, category: SankalpCategory) -> str:
        """
        Step 2: సంకల్పం (Sankalp) - Generate formal sankalp statement.
        
        NOW GPT-PERSONALIZED based on user's Rashi, Nakshatra, Deity, category, and Panchang.
        """
        from app.services.personalization_service import PersonalizationService
        
        # Generate personalized Sankalp statement via GPT
        personalization = PersonalizationService(self.db)
        sankalp_statement = await personalization.generate_sankalp_statement(user, category.value)
        
        # Add footer
        sankalp_statement = "🙏 సంకల్ప ప్రకటన\n\n" + sankalp_statement + "\n\nఈ సంకల్పం మీ విశ్వాసంతో ఫలిస్తుంది."
        
        return sankalp_statement
    
    async def send_sankalp_framed(self, user: User, category: SankalpCategory) -> bool:
        """
        Step 2: Send the formal sankalp statement.
        
        TEMPLE-STYLE FLOW:
        Chinta → Sankalp → Pariharam (FREE) → [Optional Tyagam] → Punya
        
        After Sankalp, we proceed to PARIHARAM (free ritual).
        Then we offer optional Tyagam for Annadanam seva.
        """
        statement = await self.frame_sankalp(user, category)
        
        await self.gupshup.send_text_message(
            phone=user.phone,
            message=statement,
        )
        
        # Proceed to PARIHARAM (free ritual instruction)
        return await self.send_pariharam_with_optional_tyagam(user, category)
    
    async def send_pariharam_with_optional_tyagam(self, user: User, category: SankalpCategory) -> bool:
        """
        Step 3: పరిహారం (Pariharam) - FREE ritual instruction.
        
        TEMPLE-STYLE: Give the ritual first, then softly offer optional Tyagam.
        This builds trust and feels like a temple, not a sales pitch.
        
        NOW GPT-PERSONALIZED based on user's Rashi, Nakshatra, Deity, and category.
        """
        from app.services.personalization_service import PersonalizationService
        
        # Generate personalized Pariharam via GPT
        personalization = PersonalizationService(self.db)
        pariharam = await personalization.generate_pariharam(user, category.value)
        
        # Store pariharam in conversation context for later use
        from app.models.conversation import Conversation
        from sqlalchemy import select
        result = await self.db.execute(
            select(Conversation).where(Conversation.user_id == user.id)
        )
        conversation = result.scalar_one_or_none()
        if conversation:
            conversation.set_context("last_pariharam", pariharam)
        
        deity = getattr(user, 'preferred_deity', 'other') or 'other'
        deity_telugu = DEITY_TELUGU.get(deity, "భగవంతుడు")
        
        message = f"""🙏 మీ సంకల్పం {deity_telugu} సన్నిధిలో స్వీకరించబడింది.

━━━━━━━━━━━━━━━━━━

✨ మీ పరిహారం:

🪷 {pariharam}

ఈ పరిహారాన్ని నిష్ఠగా చేయండి. మీ సంకల్పం బలపడుతుంది.

━━━━━━━━━━━━━━━━━━

🛕 అదనపు సేవ (ఐచ్ఛికం):

మీ సంకల్ప ఫలం మరింత బలపడాలంటే, అన్నదాన సేవ కూడా చేయవచ్చు.

అన్నదానం మహాపుణ్యం — అవసరమైన వారికి భోజనం అందిస్తుంది.

మీరు అన్నదాన సేవ చేయాలనుకుంటున్నారా?"""
        
        buttons = [
            {"id": "TYAGAM_YES", "title": "🙏 అవును, సేవ చేస్తాను"},
            {"id": "TYAGAM_NO", "title": "🙏 ఇప్పుడు వద్దు"},
        ]
        
        msg_id = await self.gupshup.send_button_message(
            phone=user.phone,
            body_text=message,
            buttons=buttons,
        )
        
        if msg_id:
            from app.fsm.states import ConversationState
            user_service = UserService(self.db)
            # New state: waiting for optional Tyagam decision
            await user_service.update_user_state(user, ConversationState.WAITING_FOR_TYAGAM_DECISION)
            return True
        
        return False
    
    async def handle_tyagam_decision(self, user: User, wants_tyagam: bool, category: SankalpCategory) -> bool:
        """Handle user's decision on optional Tyagam."""
        if wants_tyagam:
            # Proceed to tier selection
            return await self.send_tyagam_prompt(user, category)
        else:
            # User chose free path - send completion message
            return await self.send_free_path_completion(user, category)
    
    async def send_free_path_completion(self, user: User, category: SankalpCategory) -> bool:
        """Send completion message for users who chose Pariharam only (no payment)."""
        deity = getattr(user, 'preferred_deity', 'other') or 'other'
        deity_telugu = DEITY_TELUGU.get(deity, "భగవంతుడు")
        name = user.name or "భక్తులు"
        
        message = f"""🙏 {name} గారు,

మీ సంకల్పం {deity_telugu} సన్నిధిలో అర్పించబడింది.

మీ పరిహారం నిష్ఠగా చేయండి — మీ మనసు శాంతి పొందుతుంది.

━━━━━━━━━━━━━━━━━━

విశ్వాసంతో ఉండండి. {deity_telugu} మీకు తోడుగా ఉన్నారు.

🙏 మీకు ప్రతిరోజూ రాశిఫలాలు వస్తూనే ఉంటాయి.

ఓం శాంతి 🙏"""
        
        msg_id = await self.gupshup.send_text_message(
            phone=user.phone,
            message=message,
        )
        
        if msg_id:
            from app.fsm.states import ConversationState
            user_service = UserService(self.db)
            # Return to daily passive - they got free pariharam
            await user_service.update_user_state(user, ConversationState.DAILY_PASSIVE)
            return True
        
        return False
    
    async def send_pariharam_prompt(self, user: User, category: SankalpCategory) -> bool:
        """Legacy method - redirects to new temple-style flow."""
        return await self.send_pariharam_with_optional_tyagam(user, category)
    
    async def send_tyagam_prompt(self, user: User, category: SankalpCategory) -> bool:
        """
        Step 4: త్యాగం (Tyagam) - Offering selection.
        NOT payment, NOT donation. It's Tyagam → Seva.
        """
        message = """🙏 త్యాగం → సేవ

మీ త్యాగం ద్వారా అన్నదాన సేవ జరుగుతుంది.

"త్యాగం" అంటే వదులుకోవడం — మీ చింతను వదిలి, సేవలో మార్చడం.

మీ త్యాగ స్థాయి ఎంచుకోండి:"""
        
        buttons = [
            {"id": SankalpTier.S15.value, "title": "🪷 $21 సాముహిక"},
            {"id": SankalpTier.S30.value, "title": "🪷 $51 విశేష"},
            {"id": SankalpTier.S50.value, "title": "🪷 $108 ప్రత్యేక"},
        ]
        
        msg_id = await self.gupshup.send_button_message(
            phone=user.phone,
            body_text=message,
            buttons=buttons,
            footer="అన్నదానం: 10/25/50 కుటుంబాలకు",
        )
        
        if msg_id:
            from app.fsm.states import ConversationState
            user_service = UserService(self.db)
            await user_service.update_user_state(user, ConversationState.WAITING_FOR_TIER)
            return True
        
        return False
    
    async def create_sankalp(
        self,
        user: User,
        category: SankalpCategory,
        tier: SankalpTier,
        pariharam: Optional[str] = None,
    ) -> Sankalp:
        """Create a new sankalp record."""
        # Map tier to new amounts
        amount_map = {
            SankalpTier.S15: Decimal("21.00"),
            SankalpTier.S30: Decimal("51.00"),
            SankalpTier.S50: Decimal("108.00"),
        }
        amount = amount_map.get(tier, Decimal("21.00"))
        
        # Generate sankalp statement
        deity_telugu = DEITY_TELUGU.get(user.preferred_deity, "దేవుడు")
        name = user.name or "భక్తులు"
        sankalp_statement = f"{name} గారి కోసం, {category.display_name_telugu} సమస్య నివారణ కోసం, {deity_telugu} సన్నిధిలో"
        
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
        if not self.razorpay:
            raise ValueError("Razorpay not configured")
        
        amount_paise = int(sankalp.amount * 100)  # Convert to paise
        
        try:
            payment_link = self.razorpay.payment_link.create({
                "amount": amount_paise,
                "currency": sankalp.currency,
                "accept_partial": False,
                "description": f"సంకల్ప సేవ - {sankalp.category}",
                "customer": {
                    "contact": user.phone,
                    "name": user.name or "భక్తులు",
                },
                "notify": {
                    "sms": False,
                    "email": False,
                },
                "notes": {
                    "sankalp_id": str(sankalp.id),
                    "user_id": str(user.id),
                    "category": sankalp.category,
                },
                "callback_url": "",
                "callback_method": "get",
            })
            
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
        deity_telugu = DEITY_TELUGU.get(sankalp.deity, "దేవుడు")
        category_telugu = SankalpCategory(sankalp.category).display_name_telugu
        
        message = f"""🙏 మీ సంకల్ప వివరాలు:

📿 చింత: {category_telugu}
🙏 దేవత: {deity_telugu}
💰 త్యాగం: ${sankalp.amount}

మీ త్యాగం ద్వారా {self._get_families_fed(sankalp.tier)} కుటుంబాలకు అన్నదానం జరుగుతుంది.

👉 త్యాగం చేయడానికి ఈ లింక్ నొక్కండి:
{payment_url}

🙏 మీ సేవకు ధన్యవాదాలు."""
        
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
    
    async def send_punya_confirmation(self, user: User, sankalp: Sankalp) -> bool:
        """
        Step 5: పుణ్యం (Punya) - Merit confirmation after payment.
        
        TEMPLE-STYLE:
        User already received FREE Pariharam before payment.
        Now they get personalized Punya confirmation via GPT.
        """
        from app.services.personalization_service import PersonalizationService
        from app.models.conversation import Conversation
        from sqlalchemy import select
        
        families = self._get_families_fed(sankalp.tier)
        
        # Retrieve stored Pariharam from conversation context
        result = await self.db.execute(
            select(Conversation).where(Conversation.user_id == user.id)
        )
        conversation = result.scalar_one_or_none()
        stored_pariharam = None
        if conversation:
            stored_pariharam = conversation.get_context("last_pariharam")
        
        # If no stored pariharam, generate one
        if not stored_pariharam:
            personalization = PersonalizationService(self.db)
            stored_pariharam = await personalization.generate_pariharam(user, sankalp.category)
        
        # Generate personalized Punya confirmation via GPT
        personalization = PersonalizationService(self.db)
        message = await personalization.generate_punya_confirmation(
            user=user,
            category=sankalp.category,
            pariharam=stored_pariharam,
            families_fed=families,
            amount=float(sankalp.amount),
        )
        
        # Add receipt note
        message += "\n\n🙏 మీ రసీదు త్వరలో వస్తుంది.\n\nఓం శాంతి శాంతి శాంతిః 🙏"
        
        msg_id = await self.gupshup.send_text_message(
            phone=user.phone,
            message=message,
        )
        
        return msg_id is not None
    
    async def send_closure_message(self, user: User, sankalp: Sankalp) -> bool:
        """Alias for send_punya_confirmation."""
        return await self.send_punya_confirmation(user, sankalp)
    
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
