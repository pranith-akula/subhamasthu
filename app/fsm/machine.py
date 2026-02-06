"""
FSM Machine - Conversation state machine with strict transitions.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.fsm.states import (
    ConversationState,
    SankalpCategory,
    SankalpTier,
    Rashi,
    Deity,
    AuspiciousDay,
    Nakshatra,
)
from app.services.user_service import UserService
from app.services.gupshup_service import GupshupService
from app.services.sankalp_service import SankalpService

logger = logging.getLogger(__name__)


class FSMMachine:
    """
    Finite State Machine for conversation management.
    
    Handles transitions based on current state and user input.
    Strictly enforces valid transitions.
    """
    
    def __init__(
        self,
        db: AsyncSession,
        user: User,
        gupshup: GupshupService,
    ):
        self.db = db
        self.user = user
        self.gupshup = gupshup
        self.user_service = UserService(db)
    
    async def process_input(
        self,
        text: str,
        button_payload: Optional[str],
        message_id: str,
    ) -> None:
        """
        Process user input and handle state transitions.
        
        Args:
            text: Message text (or button title)
            button_payload: Button payload ID (if button was clicked)
            message_id: Message ID for idempotency
        """
        current_state = ConversationState(self.user.state)
        
        logger.info(f"FSM: User {self.user.phone} in state {current_state.value}, input: {text[:50] if text else button_payload}")
        
        # Route to appropriate handler based on state
        handlers = {
            ConversationState.NEW: self._handle_new,
            ConversationState.WAITING_FOR_RASHI: self._handle_rashi_selection,
            ConversationState.WAITING_FOR_NAKSHATRA: self._handle_nakshatra_selection,
            ConversationState.WAITING_FOR_BIRTH_TIME: self._handle_birth_time,
            ConversationState.WAITING_FOR_DEITY: self._handle_deity_selection,
            ConversationState.WAITING_FOR_AUSPICIOUS_DAY: self._handle_day_selection,
            ConversationState.ONBOARDED: self._handle_onboarded,
            ConversationState.DAILY_PASSIVE: self._handle_passive,
            ConversationState.WEEKLY_PROMPT_SENT: self._handle_weekly_prompt,
            ConversationState.WAITING_FOR_CATEGORY: self._handle_category_selection,
            ConversationState.WAITING_FOR_TYAGAM_DECISION: self._handle_tyagam_decision,
            ConversationState.WAITING_FOR_TIER: self._handle_tier_selection,
            ConversationState.PAYMENT_LINK_SENT: self._handle_payment_pending,
            ConversationState.PAYMENT_CONFIRMED: self._handle_payment_confirmed,
            ConversationState.COOLDOWN: self._handle_cooldown,
        }
        
        handler = handlers.get(current_state)
        if handler:
            await handler(text, button_payload)
        else:
            logger.warning(f"No handler for state: {current_state.value}")
            await self._send_default_response()
    
    async def _handle_new(self, text: str, button_payload: Optional[str]) -> None:
        """Handle NEW state - start onboarding."""
        await self._send_welcome_and_rashi_prompt()
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_RASHI)
    
    async def _handle_rashi_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle rashi selection (MANDATORY)."""
        rashi = self._parse_rashi(text, button_payload)
        
        if not rashi:
            await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="Please select your rashi from the options.",
            )
            await self._send_rashi_buttons()
            return
        
        await self.user_service.set_user_rashi(self.user, rashi)
        # Next: Ask for optional nakshatra
        await self._send_nakshatra_prompt()
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_NAKSHATRA)
    
    async def _handle_nakshatra_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle nakshatra selection (OPTIONAL - user can skip)."""
        # Check if user wants to skip
        if button_payload == "SKIP_NAKSHATRA" or text.upper() in ["SKIP", "NEXT", "VADDU"]:
            await self._send_birth_time_prompt()
            await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_BIRTH_TIME)
            return
        
        nakshatra = self._parse_nakshatra(text, button_payload)
        
        if nakshatra:
            await self.user_service.set_user_nakshatra(self.user, nakshatra)
        
        # Ask for optional birth time
        await self._send_birth_time_prompt()
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_BIRTH_TIME)
    
    async def _handle_birth_time(self, text: str, button_payload: Optional[str]) -> None:
        """Handle birth time input (OPTIONAL - user can skip)."""
        # Check if user wants to skip
        if button_payload == "SKIP_BIRTH_TIME" or text.upper() in ["SKIP", "NEXT", "VADDU"]:
            await self._send_deity_prompt()
            await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_DEITY)
            return
        
        # Try to parse birth time (HH:MM format)
        birth_time = self._parse_birth_time(text)
        
        if birth_time:
            await self.user_service.set_user_birth_time(self.user, birth_time)
        
        await self._send_deity_prompt()
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_DEITY)
    
    async def _handle_deity_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle deity selection."""
        deity = self._parse_deity(text, button_payload)
        
        if not deity:
            await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="Please select your preferred deity.",
            )
            await self._send_deity_buttons()
            return
        
        await self.user_service.set_user_deity(self.user, deity)
        await self._send_auspicious_day_prompt()
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_AUSPICIOUS_DAY)
    
    async def _handle_day_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle auspicious day selection."""
        day = self._parse_day(text, button_payload)
        
        if not day:
            await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="దయచేసి మీ శుభ దినం ఎంచుకోండి.",
            )
            await self._send_day_buttons()
            return
        
        await self.user_service.set_user_auspicious_day(self.user, day)
        
        # Mark onboarding complete with timestamp
        from datetime import datetime
        self.user.onboarded_at = datetime.utcnow()
        
        await self._send_onboarding_complete()
        await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
        
        # Day 0: Send immediate personalized Rashiphalalu
        await self._send_day_zero_rashiphalalu()
    
    async def _handle_onboarded(self, text: str, button_payload: Optional[str]) -> None:
        """Handle ONBOARDED state - transition to DAILY_PASSIVE."""
        await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
        await self._handle_passive(text, button_payload)
    
    async def _handle_passive(self, text: str, button_payload: Optional[str]) -> None:
        """Handle DAILY_PASSIVE state - user is just receiving daily messages."""
        # Any message in passive state just gets a gentle acknowledgment
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message="🙏 నమస్కారం! మీకు ప్రతిరోజూ రాశిఫలాలు వస్తాయి. మీ శుభ దినం రోజు ప్రత్యేక సందేశం వస్తుంది. శుభమస్తు! 🙏",
        )
    
    async def _handle_weekly_prompt(self, text: str, button_payload: Optional[str]) -> None:
        """Handle response to weekly prompt - same as category selection."""
        await self._handle_category_selection(text, button_payload)
    
    async def _handle_category_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle sankalp category selection."""
        category = self._parse_category(button_payload)
        
        if not category:
            await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="Please select a category for your sankalp.",
            )
            return
        
        # Store category in context and send tier selection
        sankalp_service = SankalpService(self.db)
        await sankalp_service.send_tier_selection(self.user, category)
        
        # Store category for later use
        from app.models.conversation import Conversation
        from sqlalchemy import select
        result = await self.db.execute(
            select(Conversation).where(Conversation.user_id == self.user.id)
        )
        conversation = result.scalar_one_or_none()
        if conversation:
            conversation.set_context("selected_category", category.value)
    
    async def _handle_tyagam_decision(self, text: str, button_payload: Optional[str]) -> None:
        """
        Handle user's decision on optional Tyagam (temple-style flow).
        
        TYAGAM_YES -> proceed to tier selection
        TYAGAM_NO -> complete with free Pariharam path
        """
        # Get saved category from conversation context
        from app.models.conversation import Conversation
        from sqlalchemy import select
        
        result = await self.db.execute(
            select(Conversation).where(Conversation.user_id == self.user.id)
        )
        conversation = result.scalar_one_or_none()
        
        saved_category = None
        if conversation:
            saved_category = conversation.get_context("selected_category")
        
        if not saved_category:
            # Fallback to PEACE if no category found
            saved_category = SankalpCategory.PEACE.value
        
        # Parse button response
        if button_payload == "TYAGAM_YES":
            # User wants Annadanam seva - proceed to tier selection
            sankalp_service = SankalpService(self.db)
            category = SankalpCategory(saved_category)
            await sankalp_service.send_tyagam_prompt(self.user, category)
        elif button_payload == "TYAGAM_NO":
            # User chose free Pariharam path
            sankalp_service = SankalpService(self.db)
            category = SankalpCategory(saved_category)
            await sankalp_service.send_free_path_completion(self.user, category)
        else:
            # Invalid response - resend options
            await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="🙏 దయచేసి పై బటన్లలో ఒకటి నొక్కండి.",
            )
    
    async def _handle_tier_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle sankalp tier selection."""
        tier = self._parse_tier(button_payload)
        
        if not tier:
            await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="Please select a seva tier.",
            )
            return
        
        # Get category from context
        from app.models.conversation import Conversation
        from sqlalchemy import select
        result = await self.db.execute(
            select(Conversation).where(Conversation.user_id == self.user.id)
        )
        conversation = result.scalar_one_or_none()
        category_value = conversation.get_context("selected_category") if conversation else None
        
        if not category_value:
            await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="Something went wrong. Please try again.",
            )
            await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
            return
        
        category = SankalpCategory(category_value)
        
        # Create sankalp and payment link
        sankalp_service = SankalpService(self.db)
        sankalp = await sankalp_service.create_sankalp(self.user, category, tier)
        
        try:
            payment_url = await sankalp_service.create_payment_link(sankalp, self.user)
            await sankalp_service.send_payment_link(self.user, sankalp, payment_url)
            
            # Store sankalp ID in context
            if conversation:
                conversation.set_context("pending_sankalp_id", str(sankalp.id))
        except Exception as e:
            logger.error(f"Failed to create payment link: {e}")
            await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="Sorry, there was an issue. Please try again later.",
            )
            await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
    
    async def _handle_payment_pending(self, text: str, button_payload: Optional[str]) -> None:
        """Handle messages while payment is pending."""
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message="🙏 Mee payment kosam waiting. Payment complete chesaka confirmation vastundi. 🙏",
        )
    
    async def _handle_payment_confirmed(self, text: str, button_payload: Optional[str]) -> None:
        """Handle post-payment confirmation."""
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message="🙏 Mee sankalp poorthi ayyindi! Receipt meeku vachindi. Shubham! 🙏",
        )
    
    async def _handle_cooldown(self, text: str, button_payload: Optional[str]) -> None:
        """Handle cooldown state - user completed sankalp recently."""
        from datetime import datetime, timedelta
        
        if self.user.last_sankalp_at:
            days_left = 7 - (datetime.utcnow() - self.user.last_sankalp_at).days
            days_left = max(1, days_left)
        else:
            days_left = 7
        
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message=f"🙏 Mee recent sankalp poorthi ayyindi. Mee next sankalp {days_left} days tarvaata available avtundi. Daily Rashiphalalu continue avtayi. Shubham! 🙏",
        )
    
    # === Helper methods ===
    
    async def _send_welcome_and_rashi_prompt(self) -> None:
        """Send welcome message and rashi selection."""
        welcome = """🙏 శుభమస్తు! నమస్కారం!

తెలుగు కుటుంబాల ధార్మిక సేవా వేదికకు స్వాగతం.

మీకు రోజువారీ రాశిఫలాలు, వారపు సంకల్ప అవకాశాలు, అన్నదాన సేవలు అందిస్తాము.

ముందుగా, మీ రాశి ఎంచుకోండి:"""
        
        # Due to WhatsApp button limits, we'll use a list or multiple messages
        buttons = [
            {"id": "RASHI_MESHA", "title": "మేషం (Aries)"},
            {"id": "RASHI_VRISHABHA", "title": "వృషభం (Taurus)"},
            {"id": "RASHI_MITHUNA", "title": "మిథునం (Gemini)"},
        ]
        
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text=welcome,
            buttons=buttons,
            footer="More rashis in next message",
        )
        
        # Send remaining rashis in batches
        await self._send_rashi_buttons(batch=2)
    
    async def _send_rashi_buttons(self, batch: int = 1) -> None:
        """Send rashi selection buttons in batches."""
        batches = [
            [
                {"id": "RASHI_MESHA", "title": "మేషం (Aries)"},
                {"id": "RASHI_VRISHABHA", "title": "వృషభం (Taurus)"},
                {"id": "RASHI_MITHUNA", "title": "మిథునం (Gemini)"},
            ],
            [
                {"id": "RASHI_KARKATAKA", "title": "కర్కాటకం (Cancer)"},
                {"id": "RASHI_SIMHA", "title": "సింహం (Leo)"},
                {"id": "RASHI_KANYA", "title": "కన్య (Virgo)"},
            ],
            [
                {"id": "RASHI_TULA", "title": "తుల (Libra)"},
                {"id": "RASHI_VRISHCHIKA", "title": "వృశ్చికం (Scorpio)"},
                {"id": "RASHI_DHANU", "title": "ధనుస్సు (Sagitt.)"},
            ],
            [
                {"id": "RASHI_MAKARA", "title": "మకరం (Capricorn)"},
                {"id": "RASHI_KUMBHA", "title": "కుంభం (Aquarius)"},
                {"id": "RASHI_MEENA", "title": "మీనం (Pisces)"},
            ],
        ]
        
        if batch <= len(batches):
            await self.gupshup.send_button_message(
                phone=self.user.phone,
                body_text=f"మరిన్ని రాశులు ({batch}/{len(batches)}):",
                buttons=batches[batch - 1],
            )
    
    async def _send_deity_prompt(self) -> None:
        """Send deity selection prompt."""
        buttons = [
            {"id": "DEITY_VISHNU", "title": "విష్ణువు/వేంకటేశ్వర"},
            {"id": "DEITY_SHIVA", "title": "శివుడు"},
            {"id": "DEITY_HANUMAN", "title": "హనుమాన్"},
        ]
        
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text="🙏 బాగుంది! ఇప్పుడు మీ ఇష్ట దైవాన్ని ఎంచుకోండి:",
            buttons=buttons,
        )
        
        # Send more options
        buttons2 = [
            {"id": "DEITY_LAKSHMI", "title": "లక్ష్మీ దేవి"},
            {"id": "DEITY_DURGA", "title": "దుర్గా దేవి"},
            {"id": "DEITY_GANESHA", "title": "గణపతి"},
        ]
        
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text="మరిన్ని దైవాలు:",
            buttons=buttons2,
        )
    
    async def _send_deity_buttons(self) -> None:
        """Resend deity selection buttons."""
        await self._send_deity_prompt()
    
    async def _send_nakshatra_prompt(self) -> None:
        """Send nakshatra selection prompt (OPTIONAL)."""
        # Use WhatsApp list for 27 nakshatras - first show skip option + first batch
        buttons = [
            {"id": "SKIP_NAKSHATRA", "title": "⏭️ Skip / వద్దు"},
            {"id": "NAKSH_ASHWINI", "title": "అశ్విని (Ashwini)"},
            {"id": "NAKSH_BHARANI", "title": "భరణి (Bharani)"},
        ]
        
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text="""🌟 మీ జన్మ నక్షత్రం ఏమిటి? (ఐచ్ఛికం)

తెలిస్తే ఎంచుకోండి, లేకపోతే 'వద్దు' నొక్కండి.

ఇది మీ వ్యక్తిగత రాశిఫలాలను మెరుగుపరుస్తుంది.""",
            buttons=buttons,
            footer="లేదా మీ నక్షత్రం పేరు టైప్ చేయండి",
        )
    
    async def _send_birth_time_prompt(self) -> None:
        """Send birth time prompt (OPTIONAL)."""
        buttons = [
            {"id": "SKIP_BIRTH_TIME", "title": "⏭️ Skip / వద్దు"},
        ]
        
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text="""⏰ మీ జన్మ సమయం ఏమిటి? (ఐచ్ఛికం)

ఉదా: 06:30, 14:15, 22:00

తెలిస్తే టైప్ చేయండి, లేకపోతే 'వద్దు' నొక్కండి.""",
            buttons=buttons,
        )
    
    async def _send_auspicious_day_prompt(self) -> None:
        """Send auspicious day selection prompt."""
        buttons = [
            {"id": "DAY_MONDAY", "title": "సోమవారం (Mon)"},
            {"id": "DAY_TUESDAY", "title": "మంగళవారం (Tue)"},
            {"id": "DAY_THURSDAY", "title": "గురువారం (Thu)"},
        ]
        
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text="🙏 వారపు సంకల్పానికి మీ శుభ దినం ఏది?",
            buttons=buttons,
        )
        
        buttons2 = [
            {"id": "DAY_FRIDAY", "title": "శుక్రవారం (Fri)"},
            {"id": "DAY_SATURDAY", "title": "శనివారం (Sat)"},
            {"id": "DAY_SUNDAY", "title": "ఆదివారం (Sun)"},
        ]
        
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text="మరిన్ని దినాలు:",
            buttons=buttons2,
        )
    
    async def _send_day_buttons(self) -> None:
        """Resend day selection buttons."""
        await self._send_auspicious_day_prompt()
    
    async def _send_onboarding_complete(self) -> None:
        """Send onboarding completion message."""
        # Get Telugu names for deity and day
        deity_telugu = {
            "venkateshwara": "వేంకటేశ్వర స్వామి",
            "shiva": "శివుడు",
            "vishnu": "విష్ణువు",
            "hanuman": "హనుమంతుడు",
            "durga": "దుర్గామాత",
            "lakshmi": "లక్ష్మీదేవి",
            "ganesha": "గణేషుడు",
            "saraswati": "సరస్వతీదేవి",
        }.get(self.user.preferred_deity, self.user.preferred_deity or "దేవుడు")
        
        day_telugu = {
            "monday": "సోమవారం",
            "tuesday": "మంగళవారం",
            "wednesday": "బుధవారం",
            "thursday": "గురువారం",
            "friday": "శుక్రవారం",
            "saturday": "శనివారం",
            "sunday": "ఆదివారం",
        }.get(self.user.auspicious_day, self.user.auspicious_day or "మీ శుభ దినం")
        
        # Get rashi Telugu name
        try:
            from app.fsm.states import Rashi
            rashi = Rashi(self.user.rashi)
            rashi_telugu = rashi.telugu_name
        except:
            rashi_telugu = self.user.rashi
        
        # Build preferences list in Telugu
        prefs = [
            f"📿 రాశి: {rashi_telugu}",
        ]
        
        if self.user.nakshatra:
            prefs.append(f"⭐ నక్షత్రం: {self.user.nakshatra}")
        
        if self.user.birth_time:
            prefs.append(f"⏰ జన్మ సమయం: {self.user.birth_time}")
        
        prefs.extend([
            f"🙏 ఇష్ట దైవం: {deity_telugu}",
            f"📅 శుభ దినం: {day_telugu}",
        ])
        
        prefs_str = "\n".join(prefs)
        
        message = f"""🙏✨ నమోదు పూర్తయింది! ✨🙏

మీ వివరాలు భద్రపరచబడ్డాయి:
{prefs_str}

మీకు ప్రతిరోజూ ఉదయం 7:00 గంటలకు రాశిఫలాలు వస్తాయి.
{day_telugu} రోజు ప్రత్యేక సంకల్ప అవకాశం వస్తుంది.

శుభమస్తు! 🙏"""
        
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message=message,
        )
    
    async def _send_default_response(self) -> None:
        """Send default response for unhandled states."""
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message="🙏 నమస్కారం! ఏమి సహాయం కావాలి? 🙏",
        )
    
    async def _send_day_zero_rashiphalalu(self) -> None:
        """
        Send personalized Rashiphalalu immediately after onboarding (Day 0).
        This is the user's first personalized message.
        """
        from app.services.rashiphalalu_service import RashiphalaluService
        
        try:
            rashiphalalu_service = RashiphalaluService(self.db)
            message = await rashiphalalu_service.generate_personalized_message(self.user)
            
            if message:
                # Send intro message first
                intro = """🌟 మీ మొదటి వ్యక్తిగత రాశిఫలం!

ఇప్పటి నుండి ప్రతిరోజూ ఉదయం 7 గంటలకు మీకు ఇలాంటి వ్యక్తిగత సందేశాలు వస్తాయి."""
                
                await self.gupshup.send_text_message(
                    phone=self.user.phone,
                    message=intro,
                )
                
                # Send the actual Rashiphalalu
                await self.gupshup.send_text_message(
                    phone=self.user.phone,
                    message=message,
                )
                
                # Increment rashiphalalu_days_sent (Day 0 counts as first)
                self.user.rashiphalalu_days_sent = 1
                
                logger.info(f"Day 0 Rashiphalalu sent to {self.user.phone}")
            else:
                logger.warning(f"Could not generate Day 0 Rashiphalalu for {self.user.phone}")
        except Exception as e:
            logger.error(f"Day 0 Rashiphalalu failed for {self.user.phone}: {e}")
    
    # === Parsing helpers ===
    
    def _parse_rashi(self, text: str, payload: Optional[str]) -> Optional[str]:
        """Parse rashi from input."""
        if payload and payload.startswith("RASHI_"):
            return payload.replace("RASHI_", "")
        
        # Try to match text to rashi names
        text_upper = text.upper()
        for rashi in Rashi:
            if rashi.value in text_upper or rashi.telugu_name in text:
                return rashi.value
        
        return None
    
    def _parse_deity(self, text: str, payload: Optional[str]) -> Optional[str]:
        """Parse deity from input."""
        if payload and payload.startswith("DEITY_"):
            return payload.replace("DEITY_", "")
        
        text_upper = text.upper()
        for deity in Deity:
            if deity.value in text_upper or deity.telugu_name in text:
                return deity.value
        
        return None
    
    def _parse_day(self, text: str, payload: Optional[str]) -> Optional[str]:
        """Parse auspicious day from input."""
        if payload and payload.startswith("DAY_"):
            return payload.replace("DAY_", "")
        
        text_upper = text.upper()
        for day in AuspiciousDay:
            if day.value in text_upper or day.telugu_name in text:
                return day.value
        
        return None
    
    def _parse_nakshatra(self, text: str, payload: Optional[str]) -> Optional[str]:
        """Parse nakshatra from input (OPTIONAL)."""
        if payload and payload.startswith("NAKSH_"):
            return payload.replace("NAKSH_", "")
        
        # Try to match text to nakshatra names
        text_upper = text.upper()
        for nakshatra in Nakshatra:
            if nakshatra.value in text_upper or nakshatra.telugu_name in text:
                return nakshatra.value
        
        return None
    
    def _parse_birth_time(self, text: str) -> Optional[str]:
        """Parse birth time from text input (OPTIONAL)."""
        import re
        
        # Try to match HH:MM format
        match = re.match(r'^(\d{1,2}):(\d{2})$', text.strip())
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"
        
        # Try AM/PM format conversion
        match = re.match(r'^(\d{1,2}):?(\d{2})?\s*(am|pm|AM|PM)$', text.strip())
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            is_pm = match.group(3).upper() == "PM"
            
            if hour == 12:
                hour = 0 if not is_pm else 12
            elif is_pm:
                hour += 12
            
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"
        
        return None
    
    def _parse_category(self, payload: Optional[str]) -> Optional[SankalpCategory]:
        """Parse sankalp category from button payload."""
        if not payload:
            return None
        
        try:
            return SankalpCategory(payload)
        except ValueError:
            return None
    
    def _parse_tier(self, payload: Optional[str]) -> Optional[SankalpTier]:
        """Parse sankalp tier from button payload."""
        if not payload:
            return None
        
        try:
            return SankalpTier(payload)
        except ValueError:
            return None
