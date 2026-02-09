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
from app.fsm.states import SankalpCategory, SankalpTier, SankalpStatus, AuspiciousDay, Deity
from app.services.meta_whatsapp_service import MetaWhatsappService
from app.services.user_service import UserService
from app.services.ritual_engine import RitualOrchestrator, SankalpIntensity

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
        self.whatsapp = MetaWhatsappService()
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
        from zoneinfo import ZoneInfo
        
        ist = ZoneInfo("Asia/Kolkata")
        today = datetime.now(ist).strftime("%A").upper()
        
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
        message += "\n\nమీ ఆందోళన దేని గురించి?"
        
        buttons = [
            {"id": SankalpCategory.FAMILY.value, "title": "👨‍👩‍👧 పిల్లలు/పరివారం"},
            {"id": SankalpCategory.HEALTH.value, "title": "💪 ఆరోగ్యం/రక్ష"},
            {"id": SankalpCategory.CAREER.value, "title": "💼 ఉద్యోగం/ఆర్థికం"},
        ]
        
        # USE TEMPLATE MESSAGE for 24h compliance (Weekly Re-engagement)
        # Template: weekly_sankalp_alert
        # Variables: [message]
        msg_id = await self.whatsapp.send_template_message(
            phone=user.phone,
            template_id="weekly_sankalp_alert",
            params=[message]
        )
        
        # We DO NOT send buttons here because they will fail if window is closed.
        # Instead, we wait for user to reply to the template.
        # When they reply, FSM will trigger and (since category is invalid) will resend buttons.
        
        if msg_id:
            from app.fsm.states import ConversationState
            user_service = UserService(self.db)
            # CHANGE: Start with Ritual Opening, not Category
            await user_service.update_user_state(user, ConversationState.WAITING_FOR_RITUAL_OPENING)
            return True
            
        return False

    async def send_ritual_opening(self, user: User) -> bool:
        """
        Stage 0: The Sacred Opening.
        Breathing prompt + Tithi/Day context.
        """
        from app.services.panchang_service import get_panchang_service
        
        panchang = await get_panchang_service().get_panchang()
        
        message = f"""🕯️ **ఈ క్షణంలో, మీ సంకల్ప యాత్ర ప్రారంభం అవుతుంది.**
        
ఒక నిమిషం, శ్వాసను మెల్లగా తీసుకుని వదలండి...

**ఈ రోజు:** {panchang.vara_telugu}, {panchang.tithi_telugu}
**నక్షత్రం:** {panchang.nakshatra_telugu}

మీ మనసును శాంతంగా ఉంచుకోండి.
మీరు సిద్ధంగా ఉన్నారా?"""

        buttons = [
            {"id": "START_RITUAL", "title": "🙏 సిద్ధంగా ఉన్నాను"},
        ]
        
        msg_id = await self.whatsapp.send_button_message_with_menu(
            phone=user.phone,
            body_text=message,
            buttons=buttons,
            footer="ఓం శాంతి శాంతి శాంతిః"
        )
        
        if msg_id:
            from app.fsm.states import ConversationState
            user_service = UserService(self.db)
            await user_service.update_user_state(user, ConversationState.WAITING_FOR_CATEGORY)
            return True
            
        return False

    async def send_category_selection(self, user: User) -> bool:
        """
        Send the category selection list (Stage 1 Start).
        Called after Ritual Opening.
        """
        message = "🙏 మీ మనసులో ఉన్న ప్రధానమైన చింత (వరీ) ఏమిటి?"
        
        sections = [
            {
                "title": "వర్గాలు",
                "rows": [
                    {"id": SankalpCategory.FAMILY.value, "title": "👨‍👩‍👧 పిల్లలు/పరివారం"},
                    {"id": SankalpCategory.HEALTH.value, "title": "💪 ఆరోగ్యం/రక్ష"},
                    {"id": SankalpCategory.CAREER.value, "title": "💼 ఉద్యోగం/ఆర్థికం"},
                    {"id": SankalpCategory.PEACE.value, "title": "🧘 మానసిక శాంతి"},
                ]
            }
        ]
        
        msg_id = await self.whatsapp.send_list_message(
            phone=user.phone,
            body_text=message,
            button_text="వర్గాన్ని ఎంచుకోండి",
            sections=sections,
            footer="శుభమస్తు"
        )
        
        if msg_id:
            from app.fsm.states import ConversationState
            user_service = UserService(self.db)
            await user_service.update_user_state(user, ConversationState.WAITING_FOR_CHINTA_REFLECTION)
            return True
            
        return False
    
    async def send_chinta_reflection(self, user: User, category: SankalpCategory) -> bool:
        """
        Stage 1: Hyper-Personal Reflection.
        Ask a validation question based on category.
        """
        category_prompts = {
            SankalpCategory.FAMILY: "ఈ చింత మీ గురించి, లేదా మీ కుటుంబ సభ్యుల గురించా?",
            SankalpCategory.HEALTH: "గత కొంత కాలంగా ఈ ఆరోగ్య సమస్య మిమ్మల్ని బాధిస్తోందా?",
            SankalpCategory.CAREER: "వృత్తిలో లేదా ఆర్థికంగా మీరు కోరుకున్న ఫలితం రావడం లేదా?",
            SankalpCategory.PEACE: "మనసులో ఏదో తెలియని భారం లేదా ఆందోళన ఉందా?",
        }
        
        prompt = category_prompts.get(category, "దీని గురించి క్లుప్తంగా చెప్పండి.")
        
        message = f"""🕯️ **ఆత్మ పరిశీలన**

{prompt}

(మీరు టైప్ చేసి పంపవచ్చు లేదా 'అవును' అని నొక్కవచ్చు)"""

        buttons = [
            {"id": "CONFIRM_REFLECTION", "title": "అవును (Yes)"},
        ]
        
        msg_id = await self.whatsapp.send_button_message_with_menu(
            phone=user.phone,
            body_text=message,
            buttons=buttons,
        )
        
        return msg_id is not None
        
    async def send_category_buttons(self, user: User) -> bool:
        """
        Send the category selection buttons (Global Command).
        """
        message = "🙏 మీ సంకల్పం కోసం వర్గం ఎంచుకోండి:"
        
        sections = [
            {
                "title": "వర్గాలు",
                "rows": [
                    {"id": SankalpCategory.FAMILY.value, "title": "👨‍👩‍👧 పిల్లలు/పరివారం"},
                    {"id": SankalpCategory.HEALTH.value, "title": "💪 ఆరోగ్యం/రక్ష"},
                    {"id": SankalpCategory.CAREER.value, "title": "💼 ఉద్యోగం/ఆర్థికం"},
                    {"id": SankalpCategory.PEACE.value, "title": "🧘 మానసిక శాంతి"},
                ]
            }
        ]
        
        await self.whatsapp.send_list_message(
            phone=user.phone,
            body_text=message,
            button_text="వర్గాన్ని ఎంచుకోండి",
            sections=sections,
            footer="శుభమస్తు"
        )
        
        return True
    
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
        sankalp_statement = "🙏 **సంకల్పం**\n\n" + sankalp_statement + "\n\nఈ సంకల్పం మీ విశ్వాసంతో ఫలిస్తుంది. తథాస్తు!"
        
        return sankalp_statement
    
    async def send_sankalp_confirmation(self, user: User, category: SankalpCategory) -> bool:
        """
        Stage 2: Cosmic Sankalp Confirmation.
        Send the generated Sankalp and ask for Vow (Agreement).
        """
        from app.services.personalization_service import PersonalizationService
        
        # Generator now includes Sankalp ID and Cosmic Context
        personalization = PersonalizationService(self.db)
        sankalp_statement = await personalization.generate_sankalp_statement(user, category.value)
        
        message = f"""🕯️ **మీ పవిత్ర సంకల్పం**

{sankalp_statement}

"నా సంకల్పాన్ని భగవంతుని పాదాల వద్ద ఉంచుతున్నాను." """

        buttons = [
            {"id": "AGREE_SANKALP", "title": "🙏 తథాస్తు (I Vow)"},
        ]
        
        msg_id = await self.whatsapp.send_button_message_with_menu(
            phone=user.phone,
            body_text=message,
            buttons=buttons,
            footer="ఓం తత్సత్"
        )
        
        if msg_id:
            from app.fsm.states import ConversationState
            user_service = UserService(self.db)
            await user_service.update_user_state(user, ConversationState.WAITING_FOR_SANKALP_AGREEMENT)
            return True
            
        return False
    
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
        
        # Safe conversion to telugu name
        try:
            if hasattr(deity, 'telugu_name'):
                deity_telugu = deity.telugu_name
            else:
                # Try to lookup enum from string
                deity_telugu = Deity(str(deity)).telugu_name
        except:
             deity_telugu = "భగవంతుడు"
        
        message = f"""🙏 హరి ఓం!

మీ పేరు {deity_telugu} పాదాల చెంత ఉంచబడింది. మీ సంకల్పం ఇప్పుడు ప్రారంభమైంది.

దీని పరిపూర్ణత కోసం, ఈ చిన్న పరిహారం వెంటనే చేయండి:

🪷 **పరిహారం**:
{pariharam}

-------------------

అన్నదానం ద్వారా మీ సంకల్పానికి మరింత శక్తిని జోడించాలనుకుంటున్నారా?

'మానవ సేవయే మాధవ సేవ'"""

        buttons = [
            {"id": "TYAGAM_YES", "title": "🙏 అవును, సేవ చేస్తాను"},
            {"id": "TYAGAM_NO", "title": "మరొకసారి"},
        ]
        
        msg_id = await self.whatsapp.send_button_message_with_menu(
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
        
        # Safe conversion to Telugu deity name
        try:
            if hasattr(deity, 'telugu_name'):
                deity_telugu = deity.telugu_name
            else:
                # Try to lookup enum from string
                deity_telugu = Deity(str(deity)).telugu_name
        except:
            deity_telugu = "భగవంతుడు"
        
        name = user.name or "భక్తులు"
        
        message = f"""🙏 {name} గారు,

మీ సంకల్పం {deity_telugu} సన్నిధిలో అర్పించబడింది.

మీ పరిహారం నిష్ఠగా చేయండి — మీ మనసు శాంతి పొందుతుంది.

━━━━━━━━━━━━━━━━━━

విశ్వాసంతో ఉండండి. {deity_telugu} మీకు తోడుగా ఉన్నారు.

🙏 మీకు ప్రతిరోజూ రాశిఫలాలు వస్తూనే ఉంటాయి.

ఓం శాంతి 🙏"""
        
        msg_id = await self.whatsapp.send_text_message(
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
    

    
    async def send_tyagam_prompt(self, user: User, category: SankalpCategory) -> bool:
        """
        Stage 4: Sacred Tyagam (Seva).
        
        INTENSITY-AWARE: Message tone adjusts based on user's devotional cycle.
        - GENTLE: Soft invitation, no pressure
        - STRONG: Clear value proposition
        - MEDIUM: Deeper connection framing
        - MAHA: Elevated collective positioning
        - LEADERSHIP: "Join our core circle" framing
        - COLLECTIVE: "Anchoring this community" language
        """
        # Get intensity from RitualOrchestrator
        orchestrator = RitualOrchestrator(self.db)
        intensity = orchestrator.get_sankalp_intensity(user)
        
        # Build cumulative impact reference
        total_sankalps = user.total_sankalps_count or 0
        cycle = user.devotional_cycle_number or 1
        
        # Intensity-aware message variations
        if intensity == SankalpIntensity.GENTLE:
            # Cycle 1, Week 1: Soft first-time invitation
            message = """🙏 **మీ మొదటి అన్నదాన సేవ**
            
మీరు కోరుకున్న సంకల్పం కోసం, ఆకలితో ఉన్న వారికి ఆహారం అందించడం అత్యంత పుణ్యకరం.

"మానవ సేవయే మాధవ సేవ"

మీరు ఎంత మందికి భోజనం అందించాలనుకుంటున్నారు?"""

        elif intensity == SankalpIntensity.STRONG:
            # Cycle 1, Week 4: Clear value proposition
            message = """🙏 **అన్నదాన మహా యజ్ఞం**
            
మీ సంకల్పం బలపడాలంటే, త్యాగం అవసరం.
గత వారంలో 127 కుటుంబాలకు భోజనం అందించాము.

మీరు ఎంత మందికి అన్నదానం చేయాలనుకుంటున్నారు?"""

        elif intensity == SankalpIntensity.MEDIUM:
            # Cycle 2, Week 1: Deeper connection
            impact_msg = f"మీరు ఇప్పటివరకు {total_sankalps} సంకల్పాలు పూర్తి చేశారు." if total_sankalps > 0 else ""
            message = f"""🙏 **మీ యాత్ర కొనసాగుతోంది**
            
{impact_msg}
మీ సంకల్పం మరింత బలంగా నిలబడాలంటే, సేవ ద్వారా శక్తి వస్తుంది.

మీరు ఎంత మందికి భోజనం అందించాలనుకుంటున్నారు?"""

        elif intensity == SankalpIntensity.MAHA:
            # Cycle 2, Week 4: Elevated collective
            message = f"""🙏 **మహా సంకల్ప సేవ**
            
మీరు ఇప్పటివరకు {total_sankalps} సంకల్పాలతో మార్గదర్శకంగా నిలిచారు.
ఈ వారం మనం కలిసి 500 కుటుంబాలకు చేరుకోవాలనుకుంటున్నాము.

మీరు ఎంత మందికి అన్నదానం చేయాలనుకుంటున్నారు?"""

        elif intensity == SankalpIntensity.LEADERSHIP:
            # Cycle 3+, Week 1: Core circle
            message = f"""🙏 **ప్రియమైన భక్తులారా**
            
మీరు మా ప్రధాన భక్తుల బృందంలో భాగం. {total_sankalps} సంకల్పాలతో ఎంతో మందికి ఆశ్రయం కల్పించారు.

ఈ వారం కూడా మీ సేవ కొనసాగించండి.

మీరు ఎంత మందికి భోజనం అందించాలనుకుంటున్నారు?"""

        elif intensity == SankalpIntensity.COLLECTIVE:
            # Cycle 3+, Week 4: Anchoring community
            message = f"""🙏 **మహా సమష్టి సేవ**
            
మీరు మా కమ్యూనిటీకి స్తంభంగా నిలిచారు. {total_sankalps} సంకల్పాలతో వందల కుటుంబాలకు ఆధారంగా ఉన్నారు.

ఈ మహా సేవలో మీ భాగస్వామ్యం చాలా అర్థవంతం.

మీరు ఎంత మందికి అన్నదానం చేయాలనుకుంటున్నారు?"""

        else:
            # Default / LIGHT / SILENT (should not reach here for tyagam)
            message = """🙏 **అన్నదాన మహా యజ్ఞం**
            
మీ సంకల్పం బలపడాలంటే, త్యాగం అవసరం.
"మానవ సేవయే మాధవ సేవ"

మీరు ఎంత మందికి అన్నదానం చేయాలనుకుంటున్నారు?"""
        
        # Reframed Tiers: Meals instead of just currency
        buttons = [
            {"id": SankalpTier.S15.value, "title": "10 మందికి ($21)"},
            {"id": SankalpTier.S30.value, "title": "25 మందికి ($51)"},
            {"id": SankalpTier.S81.value, "title": "40 మందికి ($81)"},
            {"id": SankalpTier.S50.value, "title": "50 మందికి ($108)"},
        ]
        
        msg_id = await self.whatsapp.send_button_message_with_menu(
            phone=user.phone,
            body_text=message,
            buttons=buttons,
            footer="ధర్మం రక్షతి రక్షితః",
        )
        
        if msg_id:
            from app.fsm.states import ConversationState
            user_service = UserService(self.db)
            await user_service.update_user_state(user, ConversationState.WAITING_FOR_TIER)
            return True
        
        return False
    
    async def send_frequency_prompt(self, user: User, tier: SankalpTier) -> bool:
        """
        Step 4b: Ask for Frequency (Monthly vs One-time).
        """
        amount_val = {
            SankalpTier.S15: "Dharmika ($21)",
            SankalpTier.S30: "Punya Vriddhi ($51)",
            SankalpTier.S81: "Visesha Sankalp ($81)",
            SankalpTier.S50: "Maha Sankalp ($108)",
        }.get(tier, "Dharmika ($21)")
        
        message = f"""🙏 **నిత్య అన్నదాన మహా యజ్ఞం**

భక్తా, దైవ కార్యంలో నిలకడ ముఖ్యం.

మీరు చేసే ఈ అన్నదానం ఒక్క రోజుతో ఆగిపోకూడదు. ప్రతీ నెల మీ పేరున పేదలకు అన్నప్రసాదం అందడం వల్ల, మీ ఇంట **అఖండ లక్ష్మీ కటాక్షం** కలుగుతుంది.

"మానవ సేవయే మాధవ సేవ"

ఈ గొప్ప కార్యాన్ని **నెలవారీ శాశ్వత సేవగా** స్వీకరించి, పుణ్యాన్ని శాశ్వతం చేసుకుంటారా?"""

        buttons = [
            {"id": "FREQ_MONTHLY", "title": "🙏 అవును, ప్రతి నెలా"},
            {"id": "FREQ_ONETIME", "title": "ఈ ఒక్కసారికి చాలు"},
        ]
        
        msg_id = await self.whatsapp.send_button_message_with_menu(
            phone=user.phone,
            body_text=message,
            buttons=buttons,
            footer="ధర్మం రక్షతి రక్షితః",
        )
        
        return msg_id is not None
    
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
            SankalpTier.S81: Decimal("81.00"),
            SankalpTier.S50: Decimal("108.00"),
        }
        amount = amount_map.get(tier, Decimal("21.00"))
        
        # Generate sankalp statement
        deity = user.preferred_deity
        try:
            if hasattr(deity, 'telugu_name'):
                deity_telugu = deity.telugu_name
            else:
                deity_telugu = Deity(str(deity)).telugu_name
        except:
             deity_telugu = "భగవంతుడు"
             
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
    
    async def create_payment_link(self, sankalp: Sankalp, user: User, is_subscription: bool = False) -> str:
        """
        Create Razorpay Link (Subscription or One-time).
        """
        if not self.razorpay:
            raise ValueError("Razorpay not configured")
        
        if is_subscription:
            # 1. Create Subscription
            try:
                plan_id = await self._get_or_create_plan(sankalp.tier, sankalp.amount, sankalp.currency)
                
                subscription = self.razorpay.subscription.create({
                    "plan_id": plan_id,
                    "customer_notify": 1,
                    "quantity": 1,
                    "total_count": 120,  # 10 years (effectively indefinite)
                    "notes": {
                        "sankalp_id": str(sankalp.id),
                        "user_id": str(user.id),
                        "category": sankalp.category,
                    }
                })
                
                sankalp.payment_link_id = subscription["id"]
                sankalp.status = SankalpStatus.PAYMENT_PENDING.value
                sankalp.razorpay_ref = {
                    "subscription_id": subscription["id"],
                    "short_url": subscription["short_url"],
                    "type": "subscription"
                }
                
                logger.info(f"Created subscription {subscription['id']} for sankalp {sankalp.id}")
                return subscription["short_url"]
                
            except Exception as e:
                logger.error(f"Subscription creation failed: {e}")
                raise
        
        else:
            # 2. Create One-Time Payment Link
            try:
                amount_paise = int(sankalp.amount * 100)
                payment_link = self.razorpay.payment_link.create({
                    "amount": amount_paise,
                    "currency": sankalp.currency,
                    "accept_partial": False,
                    "description": f"Sankalp Seva (One-Time) - {sankalp.tier} - {sankalp.category}",
                    "customer": {
                        "contact": user.phone,
                        "name": user.name or "భక్తులు",
                    },
                    "notify": {"sms": False, "email": False},
                    "notes": {
                        "sankalp_id": str(sankalp.id),
                        "user_id": str(user.id),
                    },
                    "callback_url": settings.app_url + "/payment-success",
                    "callback_method": "get",
                })
                
                sankalp.payment_link_id = payment_link["id"]
                sankalp.status = SankalpStatus.PAYMENT_PENDING.value
                sankalp.razorpay_ref = {
                    "payment_link_id": payment_link["id"],
                    "short_url": payment_link["short_url"],
                    "type": "onetime"
                }
                
                logger.info(f"Created one-time payment link {payment_link['id']} for sankalp {sankalp.id}")
                return payment_link["short_url"]
                
            except Exception as e:
                logger.error(f"Payment link creation failed: {e}")
                raise

    async def send_punya_completion(self, user: User, sankalp: Sankalp) -> bool:
        """
        Stage 5: Punya (Completion).
        Send Sankalp Patram and Friday Schedule.
        """
        from app.services.personalization_service import PersonalizationService
        personalization = PersonalizationService(self.db)
        
        # Fetch detailed confirmation message
        message = await personalization.generate_punya_confirmation(
            user=user, 
            category=sankalp.category,
            pariharam=user.get_context("last_pariharam") or "నామ జపం",
            families_fed=int(sankalp.amount // 2), # Approx calculation
            amount=float(sankalp.amount)
        )
        
        # Add Scheduling Context
        message += "\n\n🗓️ **వచ్చే శుక్రవారం** మీ పేరున మరియు మీ గోత్రం తో ప్రత్యేక పూజ జరుగుతుంది. మీకు ప్రసాదం (ఫోటో) పంపబడుతుంది.\n\nశుభమస్తు."
        
        await self.whatsapp.send_text_message(
            phone=user.phone,
            message=message
        )
        
        return True

    # Simple in-memory cache for Plan IDs to avoid API spam
    _plan_cache = {}

    async def _get_or_create_plan(self, tier: str, amount: Decimal, currency: str) -> str:
        """Get or create a Razorpay Plan for the tier (with Caching)."""
        cache_key = f"{tier}_{amount}_{currency}"
        
        # 1. Check Cache
        if cache_key in self._plan_cache:
            return self._plan_cache[cache_key]

        tier_obj = SankalpTier(tier)
        plan_name = f"Sankalp {tier_obj.display_name} Monthly"
        amount_paise = int(amount * 100)
        
        try:
            # 2. Check Razorpay (List recent plans)
            # Fetching 20 recent plans should be enough to find active ones
            plans = self.razorpay.plan.all({"count": 20})
            for plan in plans["items"]:
                if plan["item"]["amount"] == amount_paise and plan["period"] == "monthly":
                    # Found it! Cache and return
                    plan_id = plan["id"]
                    self._plan_cache[cache_key] = plan_id
                    logger.info(f"Found existing plan {plan_id} for {tier_name}")
                    return plan_id
            
            # 3. Create New Plan
            plan = self.razorpay.plan.create({
                "period": "monthly",
                "interval": 1,
                "item": {
                    "name": plan_name,
                    "amount": amount_paise,
                    "currency": currency,
                    "description": "నెలవారీ సంకల్ప సేవ"
                }
            })
            
            plan_id = plan["id"]
            self._plan_cache[cache_key] = plan_id
            logger.info(f"Created new plan {plan_id} for {tier_name}")
            return plan_id
            
        except Exception as e:
            logger.error(f"Plan fetching failed: {e}")
            raise

    async def send_payment_link(self, user: User, sankalp: Sankalp, payment_url: str) -> bool:
        """Send payment link to user via WhatsApp."""
        deity = sankalp.deity
        try:
             deity_telugu = Deity(str(deity)).telugu_name
        except:
             deity_telugu = "భగవంతుడు"
             
        category_telugu = SankalpCategory(sankalp.category).display_name_telugu
        
        message = f"""🙏 సేవా వివరాలు:

📿 చింత: {category_telugu}
🙏 దేవత: {deity_telugu}
🍎 అన్నదానం: ${sankalp.amount} ({self._get_families_fed(sankalp.tier)} మందికి)

ఈ క్రింది లింక్ ద్వారా మీ సేవను సమర్పించండి:
{payment_url}

మీ సహాయం నేరుగా ఆలయానికి చేరుతుంది. 🙏"""
        
        msg_id = await self.whatsapp.send_text_message(
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
        # Add receipt note
        message += "\n\n🙏 మీ సేవ స్వీకరించబడింది.\n\nప్రసాదం (రసీదు) త్వరలో మీకు అందుతుంది.\n\nఓం శాంతి శాంతి శాంతిః 🙏"
        
        msg_id = await self.whatsapp.send_text_message(
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
    
    # === Ritual Cadence Methods (Phase 3) ===
    
    async def send_light_blessing(self, user: User) -> bool:
        """
        Week 2: Light Blessing - Personalized collective prayer.
        Low ask, maintains warmth and connection.
        """
        from app.services.impact_service import ImpactService
        
        # Get active devotees count for personalization
        impact_service = ImpactService(self.db)
        impact = await impact_service.get_global_impact(use_cache=True)
        active_devotees = impact.get("active_devotees", 100)
        
        name = user.name or "భక్తుడు"
        
        message = f"""🙏 {name}, ఈ వారం మీ కుటుంబం కోసం సామూహిక ఆశీర్వాదం.

{active_devotees} మంది భక్తులతో కలిసి మీరు ఈ రోజు ఒక మౌన ప్రార్థనలో భాగస్వాములు.

"సర్వే జనాః సుఖినో భవంతు"

మీకు మరియు మీ కుటుంబానికి శుభం కలుగుగాక! 🙏"""
        
        msg_id = await self.whatsapp.send_text_message(
            phone=user.phone,
            message=message,
        )
        
        return msg_id is not None
    
    async def send_silent_wisdom(self, user: User) -> bool:
        """
        Week 3: Silent Wisdom - Shloka + Impact, NO ask.
        Builds trust surplus for long-term retention.
        
        Structure:
        1. Shloka
        2. Life interpretation
        3. Impact summary
        4. Gentle blessing
        """
        from app.services.impact_service import ImpactService
        
        # Get this week's impact
        impact_service = ImpactService(self.db)
        weekly = await impact_service.get_weekly_summary_data()
        personal = await impact_service.get_user_impact(user.id)
        
        meals_this_week = weekly.get("meals", 0)
        cities = weekly.get("cities", 0)
        personal_meals = personal.get("lifetime_meals", 0)
        
        # Rotating shlokas for variety
        shlokas = [
            (
                "న హి కశ్చిత్ క్షణమపి జాతు తిష్ఠత్యకర్మకృత్",
                "భగవద్గీత 3.5",
                "ఎవరూ ఒక్క క్షణం కూడా కర్మ చేయకుండా ఉండలేరు."
            ),
            (
                "యద్యదాచరతి శ్రేష్ఠః తత్తదేవేతరో జనః",
                "భగవద్గీత 3.21",
                "శ్రేష్ఠులు ఆచరించేది సామాన్యులు అనుసరిస్తారు."
            ),
            (
                "సుఖదుఃఖే సమే కృత్వా లాభాలాభౌ జయాజయౌ",
                "భగవద్గీత 2.38",
                "సుఖదుఃఖాలు, లాభనష్టాలు సమానంగా భావించు."
            ),
        ]
        
        import random
        shloka, source, interpretation = random.choice(shlokas)
        
        message = f"""🕉 ఈ వారం మీ ధ్యానం కోసం:

"{shloka}"
— {source}

{interpretation}

—

📊 ఈ వారం శుభమస్తు సమూహం:
🍚 {meals_this_week} కుటుంబాలకు అన్నదానం
📍 {cities} నగరాలలో సేవ

మీరు ఇప్పటివరకు {personal_meals} కుటుంబాలకు సేవ చేశారు.

ధర్మం రక్షతి రక్షితః 🙏"""
        
        msg_id = await self.whatsapp.send_text_message(
            phone=user.phone,
            message=message,
        )
        
        return msg_id is not None
    
    async def send_maha_sankalp(self, user: User) -> bool:
        """
        Week 4: Maha Sankalp - Elevated collective positioning.
        High ask, gated by intensity score.
        
        Feels larger than personal chinta - collective protection.
        """
        from app.services.impact_service import ImpactService
        
        # Get active devotees for social proof
        impact_service = ImpactService(self.db)
        impact = await impact_service.get_global_impact(use_cache=True)
        active_devotees = impact.get("active_devotees", 100)
        
        name = user.name or "భక్తుడు"
        
        message = f"""🙏 {name}, ఈ నెల మహా సంకల్పం ప్రారంభమైంది.

ఈ సామూహిక యజ్ఞం సమస్త భక్తుల రక్షణ & సమృద్ధి కోసం నిర్వహించబడుతోంది.

{active_devotees} మంది భక్తులు ఈ మహా సంకల్పంలో పాల్గొంటున్నారు.

మీరు కూడా ఈ దివ్య కార్యంలో భాగస్వామి కావాలనుకుంటున్నారా?"""
        
        # Send with Yes/No buttons
        msg_id = await self.whatsapp.send_interactive_buttons(
            phone=user.phone,
            body=message,
            buttons=[
                {"id": "maha_sankalp_yes", "title": "🙏 అవును"},
                {"id": "maha_sankalp_no", "title": "ఈ సారి వద్దు"},
            ]
        )
        
        if msg_id:
            # Update state
            user.state = ConversationState.WAITING_FOR_MAHA_DECISION.value if hasattr(ConversationState, 'WAITING_FOR_MAHA_DECISION') else "WAITING_FOR_MAHA_DECISION"
            user.last_sankalp_prompt_at = datetime.now(timezone.utc)
            user.sankalp_prompts_this_month = (user.sankalp_prompts_this_month or 0) + 1
        
        return msg_id is not None

