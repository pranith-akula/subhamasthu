"""
FSM Machine - Conversation state machine with strict transitions.
"""

import logging
from datetime import datetime, date, timezone
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
from sqlalchemy import select, desc
from app.models.sankalp import Sankalp
from app.fsm.states import SankalpStatus

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
        
        # --- GLOBAL COMMANDS (Bypass State Machine) ---
        clean_text = text.lower().strip() if text else ""
        if clean_text in ["history", "my seva", "my seva history", "నా సేవలు", "na sevalu", "seva list"]:
            logger.info(f"FSM: Global command '{clean_text}' detected for {self.user.phone}")
            await self._handle_history_request()
            return
        # ----------------------------------------------
        
        logger.info(f"FSM: User {self.user.phone} in state {current_state.value}, input: {text[:50] if text else button_payload}")
        
        # Route to appropriate handler based on state
        handlers = {
            ConversationState.NEW: self._handle_new,
            ConversationState.WAITING_FOR_NAME: self._handle_name_input,
            ConversationState.WAITING_FOR_RASHI: self._handle_rashi_selection,
            ConversationState.WAITING_FOR_NAKSHATRA: self._handle_nakshatra_selection,
            ConversationState.WAITING_FOR_BIRTH_TIME: self._handle_birth_time,
            ConversationState.WAITING_FOR_DEITY: self._handle_deity_selection,
            ConversationState.WAITING_FOR_AUSPICIOUS_DAY: self._handle_day_selection,
            ConversationState.WAITING_FOR_DOB: self._handle_dob_input,
            ConversationState.WAITING_FOR_ANNIVERSARY: self._handle_anniversary_input,
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
        # Send Welcome Message & Ask for Name
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message="🙏 ఓం నమో నారాయణాయ!\n\nశుభమస్తు కుటుంబంలోకి మీకు ఆత్మీయ స్వాగతం. 🌿\n\nమీ కుటుంబ క్షేమం మరియు సకల కార్య జయము కొరకు దైవ సంకల్పం.\n\nప్రారంభించడానికి, దయచేసి మీ పేరు తెలియజేయండి."
        )
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_NAME)

    async def _handle_name_input(self, text: str, button_payload: Optional[str]) -> None:
        """Handle Name input -> Ask for Deity."""
        name = text.strip()
        if not name:
             await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="దయచేసి మీ పేరును టైప్ చేయండి."
            )
             return
        
        await self.user_service.set_user_name(self.user, name)
        
        # Next: Deity (Easiest/Divine)
        await self._send_deity_prompt()
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_DEITY)
    
    async def _send_nakshatra_prompt(self) -> None:
        """Send prompt for nakshatra input (Buttons: Yes/Skip)."""
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text="☀️ అద్భుతం! మీ జన్మ నక్షత్రం వివరాలు ఇవ్వండి. (ఇది జాతక విశ్లేషణకు మరింత సహాయపడుతుంది).",
            buttons=[
                {"id": "BTN_SELECT_NAKSHATRA", "title": "నక్షత్రం ఎంచుకుంటాను"},
                {"id": "SKIP_NAKSHATRA", "title": "నాకు తెలియదు (Skip)"},
            ]
        )
        # The state should be updated to WAITING_FOR_NAKSHATRA when this prompt is sent
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_NAKSHATRA)
    
    async def _handle_rashi_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle rashi selection (MANDATORY)."""
        
        # 1. Handle Group Selection
        if button_payload == "BTN_RASHI_GRP_1":
            # Send List for Rashis 1-6
            rows = [
                {"id": f"ROW_RASHI_{r.value}", "title": r.telugu_name, "description": "రాశి ఎంచుకోండి"}
                for r in [Rashi.MESHA, Rashi.VRISHABHA, Rashi.MITHUNA, Rashi.KARKATAKA, Rashi.SIMHA, Rashi.KANYA]
            ]
            await self.gupshup.send_list_message(
                phone=self.user.phone,
                body_text="🪔 మీ రాశిని ఎంచుకోండి (1-6):",
                button_text="రాశిని ఎంచుకోండి",
                sections=[{"title": "Rashis", "rows": rows}]
            )
            return

        elif button_payload == "BTN_RASHI_GRP_2":
            # Send List for Rashis 7-12
            rows = [
                {"id": f"ROW_RASHI_{r.value}", "title": r.telugu_name, "description": "రాశి ఎంచుకోండి"}
                for r in [Rashi.TULA, Rashi.VRISHCHIKA, Rashi.DHANU, Rashi.MAKARA, Rashi.KUMBHA, Rashi.MEENA]
            ]
            await self.gupshup.send_list_message(
                phone=self.user.phone,
                body_text="🪔 మీ రాశిని ఎంచుకోండి (7-12):",
                button_text="రాశిని ఎంచుకోండి",
                sections=[{"title": "Rashis", "rows": rows}]
            )
            return

        # 2. Handle Rashi Selection (List Row or Text)
        rashi = self._parse_rashi(text, button_payload)
        
        if not rashi:
            # If invalid input, prompts again with groups
            await self.gupshup.send_button_message(
                phone=self.user.phone,
                body_text="🙏 దయచేసి మీ రాశిని ఖచ్చితంగా ఎంచుకోండి:",
                buttons=[
                    {"id": "BTN_RASHI_GRP_1", "title": "మేషం ... కన్య (1-6)"},
                    {"id": "BTN_RASHI_GRP_2", "title": "తుల ... మీనం (7-12)"}
                ]
            )
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
            
        # 1. Handle "Yes, Select" -> Show Groups
        if button_payload == "BTN_SELECT_NAKSHATRA":
            await self.gupshup.send_button_message(
                phone=self.user.phone,
                body_text="మీ నక్షత్రం ఏ గ్రూపులో ఉందో ఎంచుకోండి:",
                buttons=[
                    {"id": "BTN_NAK_GRP_1", "title": "అశ్విని ... ఆశ్లేష (1-9)"},
                    {"id": "BTN_NAK_GRP_2", "title": "మఘ ... జ్యేష్ఠ (10-18)"},
                    {"id": "BTN_NAK_GRP_3", "title": "మూల ... రేవతి (19-27)"}
                ]
            )
            return

        # 2. Handle Group Selection
        if button_payload == "BTN_NAK_GRP_1":
            rows = [{"id": f"ROW_NAK_{n.value}", "title": n.telugu_name, "description": "నక్షత్రం ఎంచుకోండి"} 
                   for n in list(Nakshatra)[:9]]
            await self.gupshup.send_list_message(
                phone=self.user.phone,
                body_text="⭐ నక్షత్రం ఎంచుకోండి (1-9):",
                button_text="నక్షత్రం",
                sections=[{"title": "నక్షత్రాలు", "rows": rows}]
            )
            return
            
        if button_payload == "BTN_NAK_GRP_2":
            rows = [{"id": f"ROW_NAK_{n.value}", "title": n.telugu_name, "description": "నక్షత్రం ఎంచుకోండి"} 
                   for n in list(Nakshatra)[9:18]]
            await self.gupshup.send_list_message(
                phone=self.user.phone,
                body_text="⭐ నక్షత్రం ఎంచుకోండి (10-18):",
                button_text="నక్షత్రం",
                sections=[{"title": "నక్షత్రాలు", "rows": rows}]
            )
            return

        if button_payload == "BTN_NAK_GRP_3":
            rows = [{"id": f"ROW_NAK_{n.value}", "title": n.telugu_name, "description": "నక్షత్రం ఎంచుకోండి"} 
                   for n in list(Nakshatra)[18:]]
            await self.gupshup.send_list_message(
                phone=self.user.phone,
                body_text="⭐ నక్షత్రం ఎంచుకోండి (19-27):",
                button_text="నక్షత్రం",
                sections=[{"title": "నక్షత్రాలు", "rows": rows}]
            )
            return
        
        # 3. Handle Nakshatra Selection
        nakshatra = self._parse_nakshatra(text, button_payload)
        
        if nakshatra:
            await self.user_service.set_user_nakshatra(self.user, nakshatra)
        else:
             # If specific selection failed but it wasn't a group select, maybe verify intent?
             # For now, if parse fails, we re-prompt.
             pass
        
        # Ask for optional birth time
        await self._send_birth_time_prompt()
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_BIRTH_TIME)
    
    async def _handle_birth_time(self, text: str, button_payload: Optional[str]) -> None:
        """Handle birth time input (OPTIONAL - user can skip)."""
        # Check if user wants to skip
        if button_payload == "SKIP_BIRTH_TIME" or text.upper() in ["SKIP", "NEXT", "VADDU", "NO"]:
            await self._finish_onboarding_flow()
            return

        # Handle "Add Time" button click - ask for text
        if button_payload == "BTN_ADD_BIRTH_TIME":
            await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="దయచేసి మీ పుట్టిన సమయాన్ని టైప్ చేయండి (ఉదాహరణకు 10:30 AM లేదా 14:30)."
            )
            return
            
        # Try to parse birth time (HH:MM format)
        birth_time = self._parse_birth_time(text)
        
        if birth_time:
            await self.user_service.set_user_birth_time(self.user, birth_time)
        
        # Finish Onboarding (Hardest step done)
        await self._finish_onboarding_flow()
    
    async def _handle_deity_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle deity selection."""
        deity = self._parse_deity(text, button_payload)
        
        if not deity:
            await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="దయచేసి మీ ఇష్ట దైవాన్ని ఎంచుకోండి.",
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
        
        # Next: Ask for DOB (Phase 2)
        await self._send_dob_prompt()
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_DOB)
    
    async def _handle_onboarded(self, text: str, button_payload: Optional[str]) -> None:
        """Handle ONBOARDED state - transition to DAILY_PASSIVE."""
        await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
        await self._handle_passive(text, button_payload)
        
    async def _handle_dob_input(self, text: str, button_payload: Optional[str]) -> None:
        """Handle DOB input (Optional) -> Ask for Rashi."""
        # Check skip
        if not (button_payload == "SKIP_DOB" or text.upper() in ["SKIP", "NEXT", "VADDU", "NO"]):
           # Parse date
           dob = self._parse_date(text)
           if dob:
               await self.user_service.set_user_dob(self.user, dob)
           else:
               # Invalid format - re-prompt or help
               await self.gupshup.send_text_message(
                   phone=self.user.phone,
                   message="తేదీ ఫార్ మాట్ అర్థం కాలేదు. దయచేసి DD-MM-YYYY (ఉదా: 15-08-1990) లా టైప్ చేయండి లేదా 'Skip' బటన్ నొక్కండి."
               )
               return

        # Next: Rashi (Mandatory - Medium Hard)
        await self._send_rashi_prompt()
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_RASHI)

    async def _finish_onboarding_flow(self) -> None:
        """Helper to mark onboarding complete and send welcome."""
        # Mark onboarding complete with timestamp
        from datetime import datetime, timezone
        self.user.onboarded_at = datetime.now(timezone.utc)
        
        await self._send_onboarding_complete()
        await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
        
        # Day 0: Send immediate personalized Rashiphalalu
        await self._send_day_zero_rashiphalalu()

    async def _handle_anniversary_input(self, text: str, button_payload: Optional[str]) -> None:
        """Handle Anniversary input (Optional) -> Finish Onboarding."""
        # Check skip
        if not (button_payload == "SKIP_ANNIVERSARY" or text.upper() in ["SKIP", "NEXT", "VADDU"]):
            anniversary = self._parse_date(text)
            if anniversary:
                await self.user_service.set_user_wedding_anniversary(self.user, anniversary)
        
        # Mark onboarding complete with timestamp
        from datetime import datetime, timezone
        self.user.onboarded_at = datetime.now(timezone.utc)
        
        await self._send_onboarding_complete()
        await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
        
        # Day 0: Send immediate personalized Rashiphalalu
        await self._send_day_zero_rashiphalalu()
    
    async def _handle_passive(self, text: str, button_payload: Optional[str]) -> None:
        """Handle DAILY_PASSIVE state - interactive menu for returning users."""
        clean_text = text.lower().strip() if text else ""
        
        # Greetings / Trigger Words
        triggers = ["om namo narayanaya", "ఓం నమో నారాయణాయ", "subhamasthu", "శుభమస్తు", "hi", "hello", "నమస్కారం"]
        
        if any(t in clean_text for t in triggers):
            # Send Main Menu
            await self.gupshup.send_button_message(
                phone=self.user.phone,
                body_text="🙏 ఓం నమో నారాయణాయ!\n\nశుభమస్తుకు స్వాగతం. మీరు ఎలా ముందుకు వెళ్లాలనుకుంటున్నారు?",
                buttons=[
                    {"id": "CMD_MY_SEVA", "title": "నా సేవలు (History)"},
                    {"id": "CMD_SANKALP", "title": "కొత్త సంకల్పం (New)"},
                    {"id": "CMD_INVITE", "title": "స్నేహితులను ఆహ్వానించండి (Invite)"},
                ],
                footer="Subhamasthu Services"
            )
            return

        # Handle Menu Clicks
        if button_payload == "CMD_MY_SEVA":
            await self._handle_history_request()
            return
            
        if button_payload == "CMD_SANKALP":
            # Trigger ad-hoc Sankalp flow
            sankalp_service = SankalpService(self.db)
            await sankalp_service.send_category_buttons(self.user)
            await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_CATEGORY)
            return

        # Default gentle acknowledgment for unknown text
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message="🙏 నమస్కారం! మీకు ప్రతిరోజూ రాశిఫలాలు వస్తాయి. సేవల కోసం 'ఓం నమో నారాయణాయ' అని పంపండి.",
        )
    
    async def _handle_weekly_prompt(self, text: str, button_payload: Optional[str]) -> None:
        """Handle response to weekly prompt - same as category selection."""
        await self._handle_category_selection(text, button_payload)
    
    async def _handle_category_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle sankalp category selection."""
        category = self._parse_category(button_payload)
        
        if not category:
            # User replied to template (or invalid input)
            # Send the actual category buttons now that window is open
            sankalp_service = SankalpService(self.db)
            await sankalp_service.send_category_buttons(self.user)
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
                message="దయచేసి సేవా స్థాయిని ఎంచుకోండి.",
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
                message="క్షమించండి, ఏదో తప్పు జరిగింది. దయచేసి మళ్ళీ ప్రయత్నించండి.",
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
                message="క్షమించండి, సాంకేతిక సమస్య ఉంది. దయచేసి కాసేపటి తర్వాత ప్రయత్నించండి.",
            )
            await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
    
    async def _handle_payment_pending(self, text: str, button_payload: Optional[str]) -> None:
        """Handle messages while payment is pending."""
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message="🙏 సేవా సమర్పణ జరుగుతోంది. దయచేసి వేచి ఉండండి. త్వరలో నిర్ధారణ వస్తుంది. 🙏",
        )
    
    async def _handle_payment_confirmed(self, text: str, button_payload: Optional[str]) -> None:
        """Handle post-payment confirmation."""
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message="🙏 మీ సంకల్పం నెరవేరింది! ప్రసాదం (రసీదు) మీకు పంపబడింది. శుభమస్తు! 🙏",
        )
    
    async def _handle_cooldown(self, text: str, button_payload: Optional[str]) -> None:
        """Handle cooldown state - user completed sankalp recently."""
        from datetime import datetime, timezone
        
        if self.user.last_sankalp_at:
            days_left = 7 - (datetime.now(timezone.utc) - self.user.last_sankalp_at).days
            days_left = max(1, days_left)
        else:
            days_left = 7
        
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message=f"🙏 హరి ఓం! మీ గత సంకల్పం పూర్తయింది. మరో {days_left} రోజుల తర్వాత మీరు మళ్ళీ సంకల్పం చేసుకోవచ్చు. అప్పటిదాకా నిత్యం రాశిఫలాలు అందుతాయి. శుభం! 🙏",
        )
    
    # === Helper methods ===
    
    async def _send_welcome_and_rashi_prompt(self) -> None:
        """Deprecated - use _handle_new and _send_rashi_prompt."""
        pass

    async def _send_rashi_prompt(self) -> None:
        """Send rashi selection prompt (Buttons)."""
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text="✨ మీ రాశి ఏ గ్రూపులో ఉంది?",
            buttons=[
                {"id": "BTN_RASHI_GRP_1", "title": "మేషం నుండి కన్య (1-6)"},
                {"id": "BTN_RASHI_GRP_2", "title": "తుల నుండి మీనం (7-12)"}
            ]
        )
    
    async def _send_deity_prompt(self) -> None:
        """Send deity selection prompt (List Message)."""
        rows = [
            {"id": "DEITY_VISHNU", "title": "శ్రీ మహా విష్ణువు", "description": "ఓం నమో నారాయణాయ"},
            {"id": "DEITY_SHIVA", "title": "పరమేశ్వరుడు (Shiva)", "description": "ఓం నమః శివాయ"},
            {"id": "DEITY_HANUMAN", "title": "ఆంజనేయ స్వామి", "description": "జై శ్రీరామ్"},
            {"id": "DEITY_LAKSHMI", "title": "శ్రీ లక్ష్మీ దేవి", "description": "ధన ప్రాప్తి కొరకు"},
            {"id": "DEITY_DURGA", "title": "శ్రీ దుర్గా మాత", "description": "రక్షణ కొరకు"},
            {"id": "DEITY_GANESHA", "title": "శ్రీ మహాగణపతి", "description": "విఘ్న నివారణ"},
            {"id": "DEITY_SAIBABA", "title": "షిరిడీ సాయిబాబా", "description": "ఓం సాయి రామ్"},
            {"id": "DEITY_VENKATESHWARA", "title": "శ్రీ వేంకటేశ్వర స్వామి", "description": "గోవిందా గోవిందా"},
        ]
        
        await self.gupshup.send_list_message(
            phone=self.user.phone,
            body_text="🌺 మీ ఇష్ట దైవం ఎవరు? (నిత్యం ఆ స్వామి అనుగ్రహం కొరకు):",
            button_text="ఇష్ట దైవం",
            sections=[{"title": "Deities", "rows": rows}]
        )
    
    async def _send_deity_buttons(self) -> None:
        """Resend deity selection buttons."""
        await self._send_deity_prompt()
    
    async def _send_nakshatra_prompt(self) -> None:
        """Send prompt for nakshatra input (Buttons: Yes/Skip)."""
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text="☀️ అద్భుతం! మీ జన్మ నక్షత్రం వివరాలు ఇవ్వండి. (ఇది జాతక విశ్లేషణకు మరింత సహాయపడుతుంది).",
            buttons=[
                {"id": "BTN_SELECT_NAKSHATRA", "title": "నక్షత్రం ఎంచుకుంటాను"},
                {"id": "SKIP_NAKSHATRA", "title": "నాకు తెలియదు (Skip)"},
            ]
        )
    
    async def _send_birth_time_prompt(self) -> None:
        """Send birth time prompt (OPTIONAL)."""
        buttons = [
            {"id": "SKIP_BIRTH_TIME", "title": "⏭️ పర్వాలేదు (Skip)"},
        ]
        
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text="""⏰ మీ జన్మ సమయం? (ఐచ్ఛికం)

ఉదా: 06:30, 14:15

ఖచ్చితమైన జాతకం కోసం ఉపయోగపడుతుంది.""",
            buttons=buttons,
        )
    
    async def _send_auspicious_day_prompt(self) -> None:
        """Send auspicious day prompt (List Message)."""
        rows = [
            {"id": "DAY_MONDAY", "title": "సోమవారం", "description": "శివుని ఆరాధన"},
            {"id": "DAY_TUESDAY", "title": "మంగళవారం", "description": "హనుమాన్/సుబ్రహ్మణ్య"},
            {"id": "DAY_WEDNESDAY", "title": "బుధవారం", "description": "విష్ణు/అయ్యప్ప"},
            {"id": "DAY_THURSDAY", "title": "గురువారం", "description": "సాయి/దత్తాత్రేయ"},
            {"id": "DAY_FRIDAY", "title": "శుక్రవారం", "description": "లక్ష్మీ/దుర్గా దేవి"},
            {"id": "DAY_SATURDAY", "title": "శనివారం", "description": "వేంకటేశ్వర/శని దేవుడు"},
            {"id": "DAY_SUNDAY", "title": "ఆదివారం", "description": "సూర్య భగవానుడు"},
        ]
        
        await self.gupshup.send_list_message(
            phone=self.user.phone,
            body_text="🗓️ వారంలో మీకు ఇష్టమైన శుభ దినం ఏది? (ఆ రోజున ప్రత్యేక సంకల్పం కోసం):",
            button_text="శుభ దినం",
            sections=[{"title": "Days", "rows": rows}]
        )
        
    async def _send_day_buttons(self) -> None:
        """Resend day selection buttons."""
        await self._send_auspicious_day_prompt()
        
    async def _send_dob_prompt(self) -> None:
        """Send DOB prompt (OPTIONAL)."""
        buttons = [
            {"id": "SKIP_DOB", "title": "⏭️ పర్వాలేదు (Skip)"},
        ]
        
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text="""🎂 మీ పుట్టినరోజు (Date of Birth) ఎప్పుడు?
            
దీని ద్వారా మీ జన్మదినాన ప్రత్యేక అర్చన మరియు ఆశీస్సులు అందించబడతాయి.

టైప్ చేయండి: DD-MM-YYYY
(ఉదాహరణ: 15-08-1990)""",
            buttons=buttons,
        )

    async def _send_anniversary_prompt(self) -> None:
        """Send Anniversary prompt (OPTIONAL)."""
        buttons = [
            {"id": "SKIP_ANNIVERSARY", "title": "⏭️ పర్వాలేదు (Skip)"},
        ]
        
        await self.gupshup.send_button_message(
            phone=self.user.phone,
            body_text="""💍 మీ పెళ్లి రోజు ఎప్పుడు? (Optional)
            
తేదీని ఇలా టైప్ చేయండి: DD-MM-YYYY
ఉదాహరణ: 21-05-2015

మీ దాంపత్య జీవితం సుఖసంతోషాలతో ఉండాలని కోరుకుంటూ...""",
            buttons=buttons,
        )
    
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
        
        prefs_str = "\n".join(prefs)
        
        message = f"""🌸 సుస్వాగతం! మీ వివరాలు స్వీకరించబడ్డాయి 🌸

{prefs_str}

✅ **నిత్యం:** ప్రతి ఉదయం 7 గంటలకు మీకు దైవ వాణి మరియు రాశిఫలాలు అందుతాయి.
✅ **వారం:** ప్రతి {day_telugu} రోజున మీకు ప్రత్యేక సంకల్పం చేసుకునే అవకాశం ఉంటుంది.

మీ జీవితం సుఖసంతోషాలతో వర్ధిల్లాలని కోరుకుంటూ...
- **శుభమస్తు కుటుంబం** 🙏"""
        
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message=message,
        )
    
    async def _send_default_response(self) -> None:
        """Send default response for unhandled states."""
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message="🙏 నమస్కారం! నేను శుభమస్తు సేవకుడిని. దయచేసి వివరంగా చెప్పండి.",
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
            return SankalpTier(payload)
        except ValueError:
            return None
            
    def _parse_date(self, text: str) -> Optional[date]:
        """Parse date from DD-MM-YYYY string."""
        from datetime import datetime, date
        import re
        
        # Clean inputs
        text = text.strip().replace('/', '-').replace('.', '-')
        
        # Match DD-MM-YYYY or DD-MM-YY
        match = re.search(r'(\d{1,2})-(\d{1,2})-(\d{2,4})', text)
        if match:
            try:
                d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
                
                # Handle 2-digit year
                if y < 100:
                    y += 2000 if y < 50 else 1900
                    
                return date(y, m, d)
            except ValueError:
                return None
                
        return None

    # === Global Handlers ===

    async def _handle_invite_request(self) -> None:
        """Handle 'invite' command - send referral link."""
        # TODO: Replace with actual bot phone number
        link = "https://wa.me/15550204780?text=Om+Namo+Narayanaya"
        
        message = f"""🙏 **శుభమస్తును విస్తరించండి**
        
మీ బంధుమిత్రులకు కూడా ప్రతిరోజూ రాశిఫలాలు మరియు దైవ సంకల్పం అందాలని కోరుకుంటున్నారా?

ఈ క్రింది లింక్ వారికి పంపండి:
{link}

"ధర్మం రక్షతి రక్షితః" 🙏"""
        
        await self.gupshup.send_text_message(
            phone=self.user.phone,
            message=message
        )

    async def _handle_history_request(self) -> None:
        """
        Handle 'history' command - show past completed sankalps.
        """
        try:
            # Fetch last 5 PAID/CLOSED sankalps
            result = await self.db.execute(
                select(Sankalp).where(
                    Sankalp.user_id == self.user.id,
                    Sankalp.status.in_([
                        SankalpStatus.PAID.value, 
                        SankalpStatus.RECEIPT_SENT.value, 
                        SankalpStatus.CLOSED.value
                    ])
                ).order_by(desc(Sankalp.created_at)).limit(5)
            )
            sankalps = result.scalars().all()
            
            if not sankalps:
                await self.gupshup.send_text_message(
                    phone=self.user.phone,
                    message="🙏 మీరు ఇప్పటివరకు ఎటువంటి సేవలు చేయలేదు. రాబోయే శుభ దినం నాడు మీ మొదటి సేవను ప్రారంభించండి! శుభమస్తు."
                )
                return
            
            # Format message
            lines = ["🙏 **మీ సేవా చరిత్ర**:\n"]
            
            total_amount = 0
            
            for idx, s in enumerate(sankalps, 1):
                # Format date: 15-Jan-2026
                date_str = s.created_at.strftime("%d-%b-%Y")
                
                # Get Telugu category name
                try:
                    cat_name = SankalpCategory(s.category).display_name_telugu
                except:
                    cat_name = s.category
                
                lines.append(f"{idx}. {cat_name} | ₹{int(s.amount)} | {date_str} ✅")
                total_amount += s.amount
                
            lines.append(f"\n✨ **మొత్తం త్యాగం: ₹{int(total_amount)}**")
            lines.append("\n🙏 ధన్యవాదాలు!")
            
            await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="\n".join(lines)
            )
            
        except Exception as e:
            logger.error(f"Error fetching history for {self.user.phone}: {e}")
            await self.gupshup.send_text_message(
                phone=self.user.phone,
                message="క్షమించండి, మీ చరిత్రను పొందడంలో సమస్య ఉంది. దయచేసి కాసేపటి తర్వాత ప్రయత్నించండి."
            )
