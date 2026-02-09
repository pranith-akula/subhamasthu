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
from app.services.user_service import UserService
from app.services.meta_whatsapp_service import MetaWhatsappService
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
        whatsapp: MetaWhatsappService,
    ):
        self.db = db
        self.user = user
        self.whatsapp = whatsapp
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

        if clean_text in ["invite", "referral", "share", "friend", "ఆహ్వానించండి", "invite friend"]:
             logger.info(f"FSM: Global command '{clean_text}' detected for {self.user.phone}")
             await self._handle_invite_request()
             return

        if clean_text in ["sankalp", "new sankalp", "kotha sankalp", "కొత్త సంకల్పం", "pooja", "puja", "seva", "సంకల్పం"]:
             logger.info(f"FSM: Global command '{clean_text}' detected for {self.user.phone}")
             # Trigger Sankalp Flow
             sankalp_service = SankalpService(self.db)
             await sankalp_service.send_category_buttons(self.user)
             await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_CATEGORY)
             return
        
        # === GLOBAL CANCEL COMMAND ===
        # Allows user to abort any flow and return to main menu
        CANCEL_KEYWORDS = [
            "cancel", "రద్దు", "menu", "మెను", "main menu", "go back", 
            "వెనక్కి", "back", "exit", "quit", "stop", "0", "ఆపు"
        ]
        
        # States that can be cancelled
        CANCELLABLE_STATES = [
            ConversationState.WAITING_FOR_CATEGORY,
            ConversationState.WAITING_FOR_CHINTA_REFLECTION,
            ConversationState.WAITING_FOR_SANKALP_AGREEMENT,
            ConversationState.WAITING_FOR_TYAGAM_DECISION,
            ConversationState.WAITING_FOR_TIER,
            ConversationState.WAITING_FOR_FREQUENCY,
            ConversationState.PAYMENT_LINK_SENT,
            ConversationState.WEEKLY_PROMPT_SENT,
            ConversationState.WAITING_FOR_RITUAL_OPENING,
            ConversationState.WAITING_FOR_MAHA_DECISION,
        ]
        
        if clean_text in CANCEL_KEYWORDS or button_payload in ["CMD_CANCEL", "CMD_MAIN_MENU"]:
            if current_state in CANCELLABLE_STATES:
                logger.info(f"FSM: User {self.user.phone} cancelled flow from {current_state.value}")
                
                # Reset to main menu
                await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
                
                # Send confirmation + main menu
                await self.whatsapp.send_button_message(
                    phone=self.user.phone,
                    body_text="🙏 రద్దు చేయబడింది.\n\nమీరు ఎలా ముందుకు వెళ్లాలనుకుంటున్నారు?",
                    buttons=[
                        {"id": "CMD_MY_SEVA", "title": "నా సేవలు"},
                        {"id": "CMD_SANKALP", "title": "కొత్త సంకల్పం"},
                        {"id": "CMD_INVITE", "title": "స్నేహితులను ఆహ్వానించండి"},
                    ],
                    footer="శుభమస్తు సేవలు"
                )
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
            ConversationState.WAITING_FOR_TRACK_SELECTION: self._handle_track_selection,
            ConversationState.WAITING_FOR_DOB: self._handle_dob_input,
            ConversationState.WAITING_FOR_ANNIVERSARY: self._handle_anniversary_input,
            ConversationState.ONBOARDED: self._handle_onboarded,
            ConversationState.DAILY_PASSIVE: self._handle_passive,
            ConversationState.WEEKLY_PROMPT_SENT: self._handle_weekly_prompt,
            ConversationState.WAITING_FOR_RITUAL_OPENING: self._handle_ritual_opening,
            ConversationState.WAITING_FOR_CATEGORY: self._handle_category_selection,
            ConversationState.WAITING_FOR_CHINTA_REFLECTION: self._handle_chinta_reflection,
            ConversationState.WAITING_FOR_SANKALP_AGREEMENT: self._handle_sankalp_agreement,
            ConversationState.WAITING_FOR_TYAGAM_DECISION: self._handle_tyagam_decision,
            ConversationState.WAITING_FOR_TIER: self._handle_tier_selection,
            ConversationState.WAITING_FOR_FREQUENCY: self._handle_frequency_selection,
            ConversationState.PAYMENT_LINK_SENT: self._handle_payment_pending,
            ConversationState.PAYMENT_CONFIRMED: self._handle_payment_confirmed,
            ConversationState.RECEIPT_SENT: self._handle_payment_confirmed,
            ConversationState.WAITING_FOR_MAHA_DECISION: self._handle_maha_decision,
        }
        
        try:
            handler = handlers.get(current_state)
            if handler:
                await handler(text, button_payload)
            else:
                logger.warning(f"No handler for state: {current_state.value}")
                await self._send_default_response()
        except Exception as e:
            logger.error(f"CRITICAL FSM ERROR for user {self.user.id}: {e}", exc_info=True)
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="🙏 క్షమించండి, సాంకేతిక సమస్య తలెత్తింది. దయచేసి కాసేపటి తర్వాత మళ్ళీ ప్రయత్నించండి."
            )
    
    async def _handle_sankalp_agreement(self, text: str, button_payload: Optional[str]) -> None:
        """
        Stage 2 -> Stage 3: Sankalp Vow -> Pariharam & Tyagam Offer.
        """
        if button_payload == "AGREE_SANKALP":
            # User took the vow.
            # Now show Pariharam (Stage 3) and offer Tyagam (Stage 4)
            # Retrieve category from context
            from app.models.conversation import Conversation
            from sqlalchemy import select
            result = await self.db.execute(
                select(Conversation).where(Conversation.user_id == self.user.id)
            )
            conversation = result.scalar_one_or_none()
            category_value = conversation.get_context("selected_category") if conversation else None
            
            if not category_value:
                 await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_CATEGORY)
                 return

            category = SankalpCategory(category_value)
            sankalp_service = SankalpService(self.db)
            await sankalp_service.send_pariharam_with_optional_tyagam(self.user, category)
            # State updated to WAITING_FOR_TYAGAM_DECISION inside service
            
        else:
            # User sent something else? Re-prompt or just proceed if positive text
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="దయచేసి 'తథాస్తు' (I Vow) అని నిర్ధారించండి."
            )

    async def _handle_ritual_opening(self, text: str, button_payload: Optional[str]) -> None:
        """
        Stage 0 -> Stage 1: Ritual Opening -> Category Selection.
        User acknowledges the opening (Breathing/Context).
        """
        sankalp_service = SankalpService(self.db)
        await sankalp_service.send_category_selection(self.user)
        # State updated to WAITING_FOR_CATEGORY inside service

    async def _handle_chinta_reflection(self, text: str, button_payload: Optional[str]) -> None:
        """
        Stage 1 -> Stage 2: Reflection -> Cosmic Sankalp.
        User confirms reflection. We validate and generate Sankalp.
        """
        # 1. Validation Message
        await self.whatsapp.send_text_message(
            phone=self.user.phone,
            message="🙏 మీ ఆవేదన అర్థమైంది. భగవంతుని సన్నిధిలో దీనికి ఉపశమనం లభిస్తుంది."
        )
        
        # 2. Proceed to Sankalp Generation (Stage 2)
        # Get category from context
        from app.models.conversation import Conversation
        from sqlalchemy import select
        result = await self.db.execute(
            select(Conversation).where(Conversation.user_id == self.user.id)
        )
        conversation = result.scalar_one_or_none()
        category_value = conversation.get_context("selected_category") if conversation else None
        
        if not category_value:
             # Fallback if context lost
             await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_CATEGORY)
             return

        category = SankalpCategory(category_value)
        sankalp_service = SankalpService(self.db)
        await sankalp_service.send_sankalp_confirmation(self.user, category)
        # State updated to WAITING_FOR_TYAGAM_DECISION inside service

    async def _handle_category_selection(self, text: str, button_payload: Optional[str]) -> None:
        """
        Stage 1 Start: Category Selection.
        """
        if not button_payload:
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="దయచేసి కింద ఉన్న బటన్స్ ఉపయోగించి ఎంచుకోండి."
            )
            return

        # NEW: Validate category enum
        try:
            category = SankalpCategory(button_payload)
        except ValueError:
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="దయచేసి సరైన ఆప్షన్ ఎంచుకోండి."
            )
            return

        # Store selection in context
        from app.models.conversation import Conversation
        from sqlalchemy import select
        result = await self.db.execute(
            select(Conversation).where(Conversation.user_id == self.user.id)
        )
        conversation = result.scalar_one_or_none()
        if conversation:
            conversation.set_context("selected_category", category.value)
            await self.db.commit()

        # Update State & Trigger Reflection (Stage 1)
        sankalp_service = SankalpService(self.db)
        # CHANGE: Go to Reflection, not Sankalp directly
        await sankalp_service.send_chinta_reflection(self.user, category)
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_CHINTA_REFLECTION)
    
    async def _handle_new(self, text: str, button_payload: Optional[str]) -> None:
        """Handle NEW state - start onboarding directly with Rashi."""
        # Clean Welcome + Rashi Prompt
        await self.whatsapp.send_text_message(
            phone=self.user.phone,
            message="🙏 ఓం నమో నారాయణాయ!\n\nశుభమస్తు కుటుంబంలోకి మీకు ఆత్మీయ స్వాగతం. 🌿\n\nమీ కోసం వ్యక్తిగత దైవ వాణి మరియు రాశిఫలాలు అందించడానికి, దయచేసి వివరాలు తెలియజేయండి."
        )
        
        # Send Rashi List directly (No groups)
        await self._send_rashi_prompt()
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_RASHI)

    async def _handle_name_input(self, text: str, button_payload: Optional[str]) -> None:
        """Handle Name input -> Ask for Deity."""
        name = text.strip()
        if not name:
             await self.whatsapp.send_text_message(
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
        await self.whatsapp.send_button_message(
            phone=self.user.phone,
            body_text="☀️ అద్భుతం! మీ జన్మ నక్షత్రం వివరాలు ఇవ్వండి. (ఇది జాతక విశ్లేషణకు మరింత సహాయపడుతుంది).",
            buttons=[
                {"id": "BTN_SELECT_NAKSHATRA", "title": "నక్షత్రం ఎంచుకుంటాను"},
                {"id": "SKIP_NAKSHATRA", "title": "నాకు తెలియదు (వద్దు)"},
            ]
        )
        # The state should be updated to WAITING_FOR_NAKSHATRA when this prompt is sent
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_NAKSHATRA)
    
    async def _handle_rashi_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle rashi selection (MANDATORY)."""
        
        if button_payload == "ROW_RASHI_MORE":
            await self._send_rashi_prompt_page_2()
            return
        
        # 2. Handle Rashi Selection (List Row or Text)
        rashi = self._parse_rashi(text, button_payload)
        
        if not rashi:
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="దయచేసి మీ రాశిని ఖచ్చితంగా ఎంచుకోండి:"
            )
            await self._send_rashi_prompt()
            return
        
        await self.user_service.set_user_rashi(self.user, rashi)
        # Next: Deity (Step 2)
        await self._send_deity_prompt()
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_DEITY)
    
    async def _handle_nakshatra_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle nakshatra selection (OPTIONAL - user can skip)."""
        # Check if user wants to skip
        if button_payload == "SKIP_NAKSHATRA" or text.upper() in ["SKIP", "NEXT", "VADDU"]:
            await self._send_birth_time_prompt()
            await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_BIRTH_TIME)
            return
            
        # 1. Handle "Yes, Select" -> Show Groups
        if button_payload == "BTN_SELECT_NAKSHATRA":
            await self.whatsapp.send_button_message(
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
            await self.whatsapp.send_list_message(
                phone=self.user.phone,
                body_text="⭐ నక్షత్రం ఎంచుకోండి (1-9):",
                button_text="నక్షత్రం",
                sections=[{"title": "నక్షత్రాలు", "rows": rows}]
            )
            return
            
        if button_payload == "BTN_NAK_GRP_2":
            rows = [{"id": f"ROW_NAK_{n.value}", "title": n.telugu_name, "description": "నక్షత్రం ఎంచుకోండి"} 
                   for n in list(Nakshatra)[9:18]]
            await self.whatsapp.send_list_message(
                phone=self.user.phone,
                body_text="⭐ నక్షత్రం ఎంచుకోండి (10-18):",
                button_text="నక్షత్రం",
                sections=[{"title": "నక్షత్రాలు", "rows": rows}]
            )
            return

        if button_payload == "BTN_NAK_GRP_3":
            rows = [{"id": f"ROW_NAK_{n.value}", "title": n.telugu_name, "description": "నక్షత్రం ఎంచుకోండి"} 
                   for n in list(Nakshatra)[18:]]
            await self.whatsapp.send_list_message(
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
            await self.whatsapp.send_text_message(
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
            await self.whatsapp.send_text_message(
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
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="దయచేసి మీ శుభ దినం ఎంచుకోండి.",
            )
            await self._send_day_buttons()
            return
        
        await self.user_service.set_user_auspicious_day(self.user, day)
        
        # Next: Track Selection (Strategic Opt)
        await self._send_track_selection_prompt()
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_TRACK_SELECTION)
    
    async def _send_track_selection_prompt(self) -> None:
        """Ask 'What matters most?' for track selection."""
        await self.whatsapp.send_button_message(
            phone=self.user.phone,
            body_text="🙏 చివరిగా ఒక చిన్న ప్రశ్న: \n\nప్రస్తుతం మీ జీవితంలో మీకు ముఖ్యమైనది ఏంటి?",
            buttons=[
                {"id": "TRACK_DEVOTION", "title": "Bhakti (Peace)"},
                {"id": "TRACK_GROWTH", "title": "Vriddhi (Growth)"},
                {"id": "TRACK_SECURITY", "title": "Raksha (Family)"}
            ]
        )

    async def _handle_track_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle track selection."""
        track = "DEVOTION" # Default
        if button_payload == "TRACK_GROWTH":
            track = "GROWTH"
        elif button_payload == "TRACK_SECURITY":
            track = "SECURITY"
            
        self.user.nurture_track = track
        # Important: Flush changes if needed, but session commit usually happens at end of request
        
        await self._finish_onboarding_flow()

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
               await self.whatsapp.send_text_message(
                   phone=self.user.phone,
                   message="తేదీ ఫార్ మాట్ అర్థం కాలేదు. దయచేసి DD-MM-YYYY (ఉదా: 15-08-1990) లా టైప్ చేయండి లేదా 'వద్దు' (Skip) బటన్ నొక్కండి."
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
            await self.whatsapp.send_button_message(
                phone=self.user.phone,
                body_text="🙏 ఓం నమో నారాయణాయ!\n\nశుభమస్తుకు స్వాగతం. మీరు ఎలా ముందుకు వెళ్లాలనుకుంటున్నారు?",
                buttons=[
                    {"id": "CMD_MY_SEVA", "title": "నా సేవలు"},
                    {"id": "CMD_SANKALP", "title": "కొత్త సంకల్పం"},
                    {"id": "CMD_INVITE", "title": "స్నేహితులను ఆహ్వానించండి"},
                ],
                footer="శుభమస్తు సేవలు"
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

        if button_payload == "CMD_INVITE":
            await self._handle_invite_request()
            return

        # Default gentle acknowledgment for unknown text
        await self.whatsapp.send_text_message(
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
        
        # Store category in context and send Sankalp Confirmation (Stage 2)
        sankalp_service = SankalpService(self.db)
        try:
            # CHANGE: Fixed crash - call send_sankalp_confirmation instead of missing send_tier_selection
            await sankalp_service.send_sankalp_confirmation(self.user, category)
            
            # Store category
            from app.models.conversation import Conversation
            from sqlalchemy import select
            result = await self.db.execute(
                select(Conversation).where(Conversation.user_id == self.user.id)
            )
            conversation = result.scalar_one_or_none()
            if conversation:
                conversation.set_context("selected_category", category.value)
                
            await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_SANKALP_AGREEMENT)
            
        except Exception as e:
            logger.error(f"Failed to handle category selection: {e}")
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="క్షమించండి, సాంకేతిక సమస్య ఉంది. దయచేసి కాసేపటి తర్వాత ప్రయత్నించండి."
            )
    
    async def _handle_sankalp_agreement(self, text: str, button_payload: Optional[str]) -> None:
        """
        Handle 'I Vow' / 'Tathastu' agreement.
        Proceed to Pariharam (Stage 3).
        """
        # Get category from context
        from app.models.conversation import Conversation
        from sqlalchemy import select
        
        result = await self.db.execute(
            select(Conversation).where(Conversation.user_id == self.user.id)
        )
        conversation = result.scalar_one_or_none()
        category_value = conversation.get_context("selected_category") if conversation else None
        
        if not category_value:
             # Fallback if context lost
             await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="క్షమించండి, సెషన్ గడువు ముగిసింది. దయచేసి 'కొత్త సంకల్పం' అని టైప్ చేయండి."
            )
             await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
             return

        category = SankalpCategory(category_value)
        sankalp_service = SankalpService(self.db)
        
        # Proceed to Pariharam + Optional Tyagam
        await sankalp_service.send_pariharam_with_optional_tyagam(self.user, category)
        
        # State update handled inside service? verify
        # send_pariharam_with_optional_tyagam updates to WAITING_FOR_TYAGAM_DECISION

    
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
        
        try:
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
                await self.whatsapp.send_text_message(
                    phone=self.user.phone,
                    message="🙏 దయచేసి పై బటన్లలో ఒకటి నొక్కండి.",
                )
        except Exception as e:
            logger.error(f"Failed to handle tyagam decision: {e}")
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="క్షమించండి, సాంకేతిక సమస్య ఉంది. దయచేసి కాసేపటి తర్వాత ప్రయత్నించండి."
            )
    
    async def _handle_maha_decision(self, text: str, button_payload: Optional[str]) -> None:
        """
        Handle Maha Sankalp decision (Week 4 collective offering).
        
        maha_sankalp_yes -> proceed to tier selection
        maha_sankalp_no -> gracefully decline, return to passive
        """
        try:
            if button_payload == "maha_sankalp_yes":
                # User wants to participate - start tier selection
                # Save category context for tier selection handler
                from app.models.conversation import Conversation
                from sqlalchemy import select
                result = await self.db.execute(
                    select(Conversation).where(Conversation.user_id == self.user.id)
                )
                conversation = result.scalar_one_or_none()
                if conversation:
                    conversation.set_context("selected_category", SankalpCategory.PEACE.value)
                
                sankalp_service = SankalpService(self.db)
                # Use PEACE as default category for Maha Sankalp (collective)
                await sankalp_service.send_tyagam_prompt(self.user, SankalpCategory.PEACE)
                
            elif button_payload == "maha_sankalp_no":
                # User declined - graceful response
                await self.whatsapp.send_text_message(
                    phone=self.user.phone,
                    message="🙏 అర్థమైంది. మీకు ప్రతిరోజూ రాశిఫలాలు వస్తూనే ఉంటాయి.\n\nఓం శాంతి 🙏"
                )
                await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
                
            else:
                # Invalid response - re-prompt gently
                await self.whatsapp.send_text_message(
                    phone=self.user.phone,
                    message="🙏 దయచేసి పై బటన్లలో ఒకటి ఎంచుకోండి."
                )
        except Exception as e:
            logger.error(f"Failed to handle maha decision: {e}", exc_info=True)
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="క్షమించండి, సాంకేతిక సమస్య ఉంది. దయచేసి కాసేపటి తర్వాత ప్రయత్నించండి."
            )
            await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
    
    async def _handle_tier_selection(self, text: str, button_payload: Optional[str]) -> None:
        """Handle sankalp tier selection."""
        tier = self._parse_tier(button_payload)
        
        if not tier:
            await self.whatsapp.send_text_message(
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
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="క్షమించండి, ఏదో తప్పు జరిగింది. దయచేసి మళ్ళీ ప్రయత్నించండి.",
            )
            await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
            return
        
        # SAVE THE TIER
        conversation.set_context("selected_tier", tier.value)
        
        sankalp_service = SankalpService(self.db)
        await sankalp_service.send_frequency_prompt(self.user, tier)
        await self.user_service.update_user_state(self.user, ConversationState.WAITING_FOR_FREQUENCY)
    
    async def _handle_frequency_selection(self, text: str, button_payload: Optional[str]) -> None:
        """
        Handle frequency selection (Monthly vs One-time).
        """
        is_subscription = False
        if button_payload == "FREQ_MONTHLY":
            is_subscription = True
        elif button_payload == "FREQ_ONETIME":
            is_subscription = False
        else:
            # Invalid input - assumption: default to one-time if lost? or prompt again?
            # Let's prompt again for clarity
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="🙏 దయచేసి పై ఆప్షన్లలో (నెలవారీ లేదా ఒక్కసారి) ఒకదాన్ని ఎంచుకోండి."
            )
            return

        # Retrieve context
        from app.models.conversation import Conversation
        from sqlalchemy import select
        result = await self.db.execute(
            select(Conversation).where(Conversation.user_id == self.user.id)
        )
        conversation = result.scalar_one_or_none()
        
        category_val = conversation.get_context("selected_category") if conversation else None
        tier_val = conversation.get_context("selected_tier") if conversation else None
        
        if not category_val or not tier_val:
             await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="క్షమించండి, సెషన్ గడువు ముగిసింది. దయచేసి మళ్ళీ ప్రారంభించండి."
            )
             await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
             return

        category = SankalpCategory(category_val)
        tier = SankalpTier(tier_val)
        
        # Create Sankalp
        sankalp_service = SankalpService(self.db)
        sankalp = await sankalp_service.create_sankalp(self.user, category, tier)
        
        try:
            # Create Link (Subscription or One-time)
            payment_url = await sankalp_service.create_payment_link(sankalp, self.user, is_subscription=is_subscription)
            await sankalp_service.send_payment_link(self.user, sankalp, payment_url)
            
            # Context Update
            if conversation:
                conversation.set_context("pending_sankalp_id", str(sankalp.id))
                
        except Exception as e:
            logger.error(f"Failed to create payment link: {e}")
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="క్షమించండి, సాంకేతిక సమస్య ఉంది. దయచేసి కాసేపటి తర్వాత ప్రయత్నించండి."
            )
            await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
    
    async def _handle_payment_pending(self, text: str, button_payload: Optional[str]) -> None:
        """Handle messages while payment is pending."""
        if button_payload:
            if button_payload in ["FREQ_MONTHLY", "FREQ_ONETIME"]:
                await self._handle_frequency_selection(text, button_payload)
                return
            if button_payload.startswith("TIER_"):
                await self._handle_tier_selection(text, button_payload)
                return

        await self.whatsapp.send_text_message(
            phone=self.user.phone,
            message="🙏 సేవా సమర్పణ జరుగుతోంది. దయచేసి వేచి ఉండండి. త్వరలో నిర్ధారణ వస్తుంది. 🙏",
        )
    
    async def _handle_payment_confirmed(self, text: str, button_payload: Optional[str]) -> None:
        """Handle post-payment confirmation."""
        await self.whatsapp.send_text_message(
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
        
        await self.whatsapp.send_text_message(
            phone=self.user.phone,
            message=f"🙏 హరి ఓం! మీ గత సంకల్పం పూర్తయింది. మరో {days_left} రోజుల తర్వాత మీరు మళ్ళీ సంకల్పం చేసుకోవచ్చు. అప్పటిదాకా నిత్యం రాశిఫలాలు అందుతాయి. శుభం! 🙏",
        )
    
    # === Helper methods ===
    
    async def _send_welcome_and_rashi_prompt(self) -> None:
        """Deprecated - use _handle_new and _send_rashi_prompt."""
        pass

    async def _send_rashi_prompt(self) -> None:
        """
        Send rashi selection prompt (Paginated).
        WhatsApp List Message limit is 10 rows. We have 12 Rashis.
        Strategy: Show first 9 + 'More'.
        """
        # Rashis 1-9 (Mesha to Dhanu)
        paginated_rashis = [
            Rashi.MESHA, Rashi.VRISHABHA, Rashi.MITHUNA, Rashi.KARKATAKA, 
            Rashi.SIMHA, Rashi.KANYA, Rashi.TULA, Rashi.VRISHCHIKA, Rashi.DHANU
        ]
        
        rows = [
            {"id": f"ROW_RASHI_{r.value}", "title": r.telugu_name, "description": ""}
            for r in paginated_rashis
        ]
        
        # Add "More" option as 10th row
        rows.append({
            "id": "ROW_RASHI_MORE",
            "title": "👇 ఇంకా ఉన్నాయి... (More)",
            "description": "మిగతా రాశులు చూడండి"
        })

        await self.whatsapp.send_list_message(
            phone=self.user.phone,
            body_text="✨ మీ రాశిని ఎంచుకోండి:",
            button_text="రాశిని ఎంచుకోండి",
            sections=[
                {"title": "రాశులు (1-9)", "rows": rows}
            ]
        )

    async def _send_rashi_prompt_page_2(self) -> None:
        """Send remaining rashis (10-12)."""
        # Rashis 10-12 (Makara to Meena)
        paginated_rashis = [Rashi.MAKARA, Rashi.KUMBHA, Rashi.MEENA]
        
        rows = [
            {"id": f"ROW_RASHI_{r.value}", "title": r.telugu_name, "description": ""}
            for r in paginated_rashis
        ]
        
        await self.whatsapp.send_list_message(
            phone=self.user.phone,
            body_text="✨ మిగతా రాశులు:",
            button_text="రాశిని ఎంచుకోండి",
            sections=[
                {"title": "రాశులు (10-12)", "rows": rows}
            ]
        )
    
    async def _send_deity_prompt(self) -> None:
        """Send deity selection prompt (List Message)."""
        rows = [
            {"id": "DEITY_VISHNU", "title": "శ్రీ మహా విష్ణువు", "description": "ఓం నమో నారాయణాయ"},
            {"id": "DEITY_SHIVA", "title": "పరమేశ్వరుడు", "description": "ఓం నమః శివాయ"},
            {"id": "DEITY_HANUMAN", "title": "ఆంజనేయ స్వామి", "description": "జై శ్రీరామ్"},
            {"id": "DEITY_LAKSHMI", "title": "శ్రీ లక్ష్మీ దేవి", "description": "ధన ప్రాప్తి కొరకు"},
            {"id": "DEITY_DURGA", "title": "శ్రీ దుర్గా మాత", "description": "రక్షణ కొరకు"},
            {"id": "DEITY_GANESHA", "title": "శ్రీ మహాగణపతి", "description": "విఘ్న నివారణ"},
            {"id": "DEITY_SAIBABA", "title": "షిరిడీ సాయిబాబా", "description": "ఓం సాయి రామ్"},
            {"id": "DEITY_VENKATESHWARA", "title": "శ్రీ వేంకటేశ్వర స్వామి", "description": "గోవిందా గోవిందా"},
        ]
        
        await self.whatsapp.send_list_message(
            phone=self.user.phone,
            body_text="🌺 మీ ఇష్ట దైవం ఎవరు? (నిత్యం ఆ స్వామి అనుగ్రహం కొరకు):",
            button_text="ఇష్ట దైవం",
            sections=[{"title": "ఇష్ట దైవాలు", "rows": rows}]
        )
    
    async def _send_deity_buttons(self) -> None:
        """Resend deity selection buttons."""
        await self._send_deity_prompt()
    
    async def _send_nakshatra_prompt(self) -> None:
        """Send prompt for nakshatra input (Buttons: Yes/Skip)."""
        await self.whatsapp.send_button_message(
            phone=self.user.phone,
            body_text="☀️ అద్భుతం! మీ జన్మ నక్షత్రం వివరాలు ఇవ్వండి. (ఇది జాతక విశ్లేషణకు మరింత సహాయపడుతుంది).",
            buttons=[
                {"id": "BTN_SELECT_NAKSHATRA", "title": "నక్షత్రం ఎంచుకుంటాను"},
                {"id": "SKIP_NAKSHATRA", "title": "నాకు తెలియదు (వద్దు)"},
            ]
        )
    
    async def _send_birth_time_prompt(self) -> None:
        """Send birth time prompt (OPTIONAL)."""
        buttons = [
            {"id": "SKIP_BIRTH_TIME", "title": "⏭️ పర్వాలేదు (వద్దు)"},
        ]
        
        await self.whatsapp.send_button_message(
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
        
        await self.whatsapp.send_list_message(
            phone=self.user.phone,
            body_text="🗓️ వారంలో మీకు ఇష్టమైన శుభ దినం ఏది? (ఆ రోజున ప్రత్యేక సంకల్పం కోసం):",
            button_text="శుభ దినం",
            sections=[{"title": "శుభ దినాలు", "rows": rows}]
        )
        
    async def _send_day_buttons(self) -> None:
        """Resend day selection buttons."""
        await self._send_auspicious_day_prompt()
        
    async def _send_dob_prompt(self) -> None:
        """Send DOB prompt (OPTIONAL)."""
        buttons = [
            {"id": "SKIP_DOB", "title": "⏭️ పర్వాలేదు (వద్దు)"},
        ]
        
        await self.whatsapp.send_button_message(
            phone=self.user.phone,
            body_text="""🎂 మీ పుట్టినరోజు ఎప్పుడు?
            
దీని ద్వారా మీ జన్మదినాన ప్రత్యేక అర్చన మరియు ఆశీస్సులు అందించబడతాయి.

టైప్ చేయండి: DD-MM-YYYY
(ఉదాహరణ: 15-08-1990)""",
            buttons=buttons,
        )

    async def _send_anniversary_prompt(self) -> None:
        """Send Anniversary prompt (OPTIONAL)."""
        buttons = [
            {"id": "SKIP_ANNIVERSARY", "title": "⏭️ పర్వాలేదు (వద్దు)"},
        ]
        
        await self.whatsapp.send_button_message(
            phone=self.user.phone,
            body_text="""💍 మీ పెళ్లి రోజు ఎప్పుడు? (ఐచ్ఛికం)
            
తేదీని ఇలా టైప్ చేయండి: DD-MM-YYYY
ఉదాహరణ: 21-05-2015

మీ దాంపత్య జీవితం సుఖసంతోషాలతో ఉండాలని కోరుకుంటూ...""",
            buttons=buttons,
        )
    
    async def _send_onboarding_complete(self) -> None:
        """Send onboarding completion message."""
        # Just a simple confirmation - content comes next
        await self.whatsapp.send_text_message(
            phone=self.user.phone,
            message="🌸 మీ వివరాలు నమోదు చేయబడ్డాయి. ధన్యవాదాలు! 🙏",
        )
    
    async def _send_default_response(self) -> None:
        """Send default response for unhandled states."""
        await self.whatsapp.send_text_message(
            phone=self.user.phone,
            message="🙏 నమస్కారం! నేను శుభమస్తు సేవకుడిని. దయచేసి వివరంగా చెప్పండి.",
        )
    
    async def _finish_onboarding_flow(self) -> None:
        """Complete onboarding, save state, send Day 0 content."""
        # 1. Update State
        await self.user_service.update_user_state(self.user, ConversationState.DAILY_PASSIVE)
        
        # 2. Send Confirmation (No Summary)
        await self.whatsapp.send_text_message(
            phone=self.user.phone,
            message="🌸 మీ వివరాలు నమోదు చేయబడ్డాయి. ధన్యవాదాలు! 🙏"
        )
        
        # 3. Send Day 0 Rashiphalalu
        await self._send_day_zero_rashiphalalu()

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
                
                await self.whatsapp.send_text_message(
                    phone=self.user.phone,
                    message=intro,
                )
                
                # Send the actual Rashiphalalu
                await self.whatsapp.send_text_message(
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
        """Handle 'invite' command - send referral link with CTA button."""
        # Generic Share Link (opens contact picker)
        from app.config import settings
        bot_number = settings.whatsapp_phone_number
        
        share_text = f"నమస్కారం! నేను శుభమస్తు ద్వారా ప్రతిరోజూ దైవ సంకల్పం తీసుకుంటున్నాను. ఇది నాకు ఎంతో శాంతిని ఇస్తోంది. మీరు కూడా ప్రయత్నించండి: https://wa.me/{bot_number}?text=Om+Namo+Narayanaya"
        
        from urllib.parse import quote
        encoded_text = quote(share_text)
        link = f"https://wa.me/?text={encoded_text}"
        
        message = """🙏 **శుభమస్తును విస్తరించండి**
        
మీ బంధుమిత్రులకు కూడా ప్రతిరోజూ రాశిఫలాలు మరియు దైవ సంకల్పం అందాలని కోరుకుంటున్నారా?

క్రింది బటన్ నొక్కి వారికి షేర్ చేయండి:"""

        await self.whatsapp.send_cta_url_message(
            phone=self.user.phone,
            body_text=message,
            button_text="స్నేహితులతో పంచుకోండి",
            url=link,
            footer="ధర్మం రక్షతి రక్షితః"
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
                await self.whatsapp.send_text_message(
                    phone=self.user.phone,
                    message="🙏 మీరు ఇప్పటివరకు ఎటువంటి సేవలు చేయలేదు. రాబోయే శుభ దినం నాడు మీ మొదటి సేవను ప్రారంభించండి! శుభమస్తు."
                )
                return
            
            # Format message
            lines = ["🙏 **మీ సేవా చరిత్ర**:\n"]
            
            total_amount = 0
            
            for idx, s in enumerate(sankalps, 1):
                # Format date: 15-01-2026
                date_str = s.created_at.strftime("%d-%m-%Y")
                
                # Get Telugu category name
                try:
                    cat_name = SankalpCategory(s.category).display_name_telugu
                except:
                    cat_name = s.category
                
                lines.append(f"{idx}. {cat_name} | ₹{int(s.amount)} | {date_str} ✅")
                total_amount += s.amount
                
            lines.append(f"\n✨ **మొత్తం త్యాగం: ₹{int(total_amount)}**")
            lines.append("\n🙏 ధన్యవాదాలు!")
            
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="\n".join(lines)
            )
            
        except Exception as e:
            logger.error(f"Error fetching history for {self.user.phone}: {e}")
            await self.whatsapp.send_text_message(
                phone=self.user.phone,
                message="క్షమించండి, మీ చరిత్రను పొందడంలో సమస్య ఉంది. దయచేసి కాసేపటి తర్వాత ప్రయత్నించండి."
            )
