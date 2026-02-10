"""
Rashiphalalu Service - Personalized daily horoscope generation in pure Telugu.
Uses Vedic astrology principles and classical structure.
"""

import logging
from datetime import date, datetime
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

from app.config import settings
from app.models.rashiphalalu import RashiphalaluCache
from app.models.user import User
from app.fsm.states import Rashi
from app.services.meta_whatsapp_service import MetaWhatsappService
from app.services.panchang_service import get_panchang_service, PanchangData

logger = logging.getLogger(__name__)

# OpenAI async client
client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None


# Rashi symbols
RASHI_SYMBOLS = {
    "mesha": "♈",
    "vrushabha": "♉",
    "mithuna": "♊",
    "karkataka": "♋",
    "simha": "♌",
    "kanya": "♍",
    "tula": "♎",
    "vrischika": "♏",
    "dhanu": "♐",
    "makara": "♑",
    "kumbha": "♒",
    "meena": "♓",
}

# Deity blessings in Telugu
DEITY_BLESSINGS = {
    "venkateshwara": ("వేంకటేశ్వర స్వామి", "ఓం నమో వేంకటేశాయ నమః"),
    "shiva": ("శివుడు", "ఓం నమః శివాయ"),
    "vishnu": ("విష్ణువు", "ఓం నమో నారాయణాయ"),
    "hanuman": ("హనుమంతుడు", "ఓం శ్రీ హనుమతే నమః"),
    "durga": ("దుర్గామాత", "ఓం దుం దుర్గాయై నమః"),
    "lakshmi": ("లక్ష్మీదేవి", "ఓం శ్రీ మహాలక్ష్మ్యై నమః"),
    "saraswati": ("సరస్వతీదేవి", "ఓం ఐం సరస్వత్యై నమః"),
    "ganesh": ("గణేషుడు", "ఓం శ్రీ గణేశాయ నమః"),
    "rama": ("శ్రీరాముడు", "శ్రీ రామ జయ రామ జయ జయ రామ"),
    "krishna": ("శ్రీకృష్ణుడు", "హరే కృష్ణ హరే కృష్ణ"),
    "ayyappa": ("అయ్యప్ప", "స్వామియే శరణం అయ్యప్ప"),
    "subrahmanya": ("సుబ్రహ్మణ్యస్వామి", "ఓం సుబ్రహ్మణ్యాయ నమః"),
    "other": ("భగవంతుడు", "ఓం శాంతి శాంతి శాంతిః"),
}


class RashiphalaluService:
    """Service for generating personalized daily Rashiphalalu in Telugu."""
    
    PROMPT_VERSION = "v2"
    
    # Model is configurable via OPENAI_MODEL env var
    @property
    def model(self) -> str:
        return settings.openai_model or "gpt-4o-mini"
    
    # Pure Telugu system prompt with classical structure
    SYSTEM_PROMPT = """నీవు అనుభవజ్ఞుడైన వేద జ్యోతిష్య పండితుడివి. తెలుగు కుటుంబాలకు వ్యక్తిగత రాశిఫలాలు అందించే పవిత్ర బాధ్యత నీది.

నీ రాశిఫలాలు:
- పూర్తిగా తెలుగులో ఉండాలి (ఏ ఆంగ్లం వద్దు, english script వాడకూడదు).
- ఇంగ్లీష్ లిపిలో తెలుగు రాయకూడదు (Do not use English script for Telugu words).
- ఆశావహంగా, ధైర్యం కలిగించేలా ఉండాలి
- భయం, ఆందోళన కలిగించకూడదు
- వేద/పురాణ ఆధారంగా శాస్త్రీయంగా ఉండాలి
- సరళంగా, అందరికీ అర్థమయ్యేలా ఉండాలి
- WhatsApp కు తగినట్లు క్లుప్తంగా ఉండాలి

ప్రతి విభాగం ఒకటి నుండి రెండు వాక్యాలు మాత్రమే రాయి.

శైలి: పండితుని వలె హుందాగా, కానీ స్నేహపూర్వకంగా.
స్వరం: ఆశ్వాసన > భయం, ధైర్యం > నిరాశ."""

    # Structured output template
    OUTPUT_TEMPLATE = """🙏 ఓం శ్రీ గురుభ్యో నమః

శుభోదయం {name}!

📅 {date_telugu}, {vara}
🌙 {paksha}, {tithi} తిథి
⭐ {nakshatra} నక్షత్రం

{rashi_symbol} {rashi_telugu} రాశి - ఈ రోజు ఫలాలు

🪐 గ్రహ స్థితి: {graha_sthiti}

🔮 సమగ్ర ఫలం:
{overall_prediction}

💼 ఉద్యోగం/వ్యాపారం: {career}

💰 ఆర్థికం: {finance}

❤️ కుటుంబం: {family}

💪 ఆరోగ్యం: {health}

✨ ప్రత్యేక సూచన: {remedy}

━━━━━━━━━━━━━━━━━━━━
🌟 శుభ సమయం: {auspicious_time}
🎨 శుభ వర్ణం: {lucky_color}
🔢 శుభ అంకం: {lucky_number}
━━━━━━━━━━━━━━━━━━━━

🙏 {deity_name} ఆశీర్వాదం:
"{deity_mantra}"

ఓం శాంతి శాంతి శాంతిః 🙏"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.whatsapp = MetaWhatsappService()
        self.panchang = get_panchang_service()
    
    async def generate_personalized_message(self, user: User, target_date: Optional[date] = None) -> Optional[str]:
        """
        Generate a personalized Rashiphalalu message for a specific user.
        
        Uses user's:
        - Rashi (mandatory)
        - Nakshatra (if available)
        - Preferred deity
        - Name
        """
        if not user.rashi:
            logger.warning(f"User {user.phone} has no rashi set")
            return None
        
        if target_date is None:
            target_date = date.today()
        
        if not client:
            logger.error("OpenAI client not configured")
            return None
        
        # Get panchang data
        panchang = await self.panchang.get_panchang(target_date)
        
        # Get rashi info
        try:
            rashi = Rashi(user.rashi)
            rashi_telugu = rashi.telugu_name
        except ValueError:
            rashi_telugu = user.rashi
        
        # Get user's nakshatra
        user_nakshatra = getattr(user, 'nakshatra', None) or "తెలియదు"
        
        # Get deity info
        deity = getattr(user, 'preferred_deity', 'other') or 'other'
        deity_name, deity_mantra = DEITY_BLESSINGS.get(deity, DEITY_BLESSINGS['other'])
        
        # Get user name
        user_name = getattr(user, 'name', None) or ""
        if not user_name:
            user_name = "భక్తులకు"
        
        # Format date in Telugu
        date_telugu = self._format_date_telugu(target_date)
        
        # Build the user prompt
        user_prompt = f"""ఈ రోజు వివరాలు:
- తేది: {date_telugu}
- వారం: {panchang.vara_telugu}
- తిథి: {panchang.tithi_telugu}
- పక్షం: {panchang.paksha}
- నక్షత్రం: {panchang.nakshatra_telugu}
- గ్రహ స్థితి: {panchang.graha_sthiti}

వినియోగదారు వివరాలు:
- రాశి: {rashi_telugu}
- జన్మ నక్షత్రం: {user_nakshatra}
- ఇష్ట దైవం: {deity_name}

దయచేసి ఈ రాశికి ఈ రోజు ఫలాలు రాయండి:
1. సమగ్ర ఫలం (2-3 వాక్యాలు)
2. ఉద్యోగం/వ్యాపారం (1 వాక్యం)
3. ఆర్థికం (1 వాక్యం)
4. కుటుంబం (1 వాక్యం)
5. ఆరోగ్యం (1 వాక్యం)
6. ప్రత్యేక సూచన/పరిహారం (1 వాక్యం)
7. శుభ సమయం, వర్ణం, అంకం

JSON ఫార్మాట్‌లో సమాధానం ఇవ్వండి:
{{"overall": "...", "career": "...", "finance": "...", "family": "...", "health": "...", "remedy": "...", "auspicious_time": "...", "lucky_color": "...", "lucky_number": "..."}}"""

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=500,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            
            import json
            content = response.choices[0].message.content.strip()
            predictions = json.loads(content)
            
            # Format the final message
            rashi_symbol = RASHI_SYMBOLS.get(user.rashi.lower(), "🔮")
            
            message = self.OUTPUT_TEMPLATE.format(
                name=user_name,
                date_telugu=date_telugu,
                vara=panchang.vara_telugu,
                paksha=panchang.paksha,
                tithi=panchang.tithi_telugu,
                nakshatra=panchang.nakshatra_telugu,
                rashi_symbol=rashi_symbol,
                rashi_telugu=rashi_telugu,
                graha_sthiti=panchang.graha_sthiti,
                overall_prediction=predictions.get("overall", "శుభదినం"),
                career=predictions.get("career", "కార్యములు సిద్ధిస్తాయి"),
                finance=predictions.get("finance", "ఆర్థిక స్థిరత్వం ఉంటుంది"),
                family=predictions.get("family", "కుటుంబంలో సంతోషం"),
                health=predictions.get("health", "ఆరోగ్యం బాగుంటుంది"),
                remedy=predictions.get("remedy", "ఇష్ట దైవాన్ని స్మరించండి"),
                auspicious_time=predictions.get("auspicious_time", "ఉదయం 9-11"),
                lucky_color=predictions.get("lucky_color", "పసుపు"),
                lucky_number=predictions.get("lucky_number", "3"),
                deity_name=deity_name,
                deity_mantra=deity_mantra,
            )
            
            logger.info(f"Generated personalized rashiphalalu for {user.phone}")
            return message
            
        except Exception as e:
            logger.error(f"Failed to generate personalized message: {e}")
            return None
    
    def _format_date_telugu(self, target_date: date) -> str:
        """Format date in Telugu."""
        telugu_months = {
            1: "జనవరి", 2: "ఫిబ్రవరి", 3: "మార్చి", 4: "ఏప్రిల్",
            5: "మే", 6: "జూన్", 7: "జూలై", 8: "ఆగస్టు",
            9: "సెప్టెంబర్", 10: "అక్టోబర్", 11: "నవంబర్", 12: "డిసెంబర్",
        }
        month = telugu_months.get(target_date.month, str(target_date.month))
        return f"{target_date.day} {month} {target_date.year}"
    
    async def generate_daily_messages(self, target_date: Optional[date] = None) -> int:
        """
        Generate Rashiphalalu for all 12 rashis for the given date (cached version).
        
        Returns count of messages generated.
        """
        if target_date is None:
            target_date = date.today()
        
        generated = 0
        
        for rashi in Rashi:
            # Check if already generated
            existing = await self._get_cached_message(target_date, rashi.value)
            if existing:
                logger.debug(f"Rashiphalalu for {rashi.value} on {target_date} already exists")
                continue
            
            # Generate via OpenAI
            message = await self._generate_for_rashi(target_date, rashi)
            
            if message:
                # Cache the message
                cache_entry = RashiphalaluCache(
                    date=target_date,
                    rashi=rashi.value,
                    language_variant="te",  # Pure Telugu now
                    message_text=message,
                    model=self.MODEL,
                    prompt_version=self.PROMPT_VERSION,
                )
                self.db.add(cache_entry)
                generated += 1
        
        await self.db.flush()
        logger.info(f"Generated {generated} Rashiphalalu messages for {target_date}")
        return generated
    
    async def broadcast_to_users(self, target_date: Optional[date] = None) -> int:
        """
        Broadcast personalized Rashiphalalu to all active users.
        Increments rashiphalalu_days_sent for 6-day Sankalp eligibility.
        
        Returns count of messages sent.
        """
        if target_date is None:
            target_date = date.today()
        
        sent = 0
        
        # Get all active users with rashi set
        users = await self._get_active_users()
        
        for user in users:
            try:
                # Generate personalized message for each user
                message = await self.generate_personalized_message(user, target_date)
                
                if message:
                    # USE TEMPLATE MESSAGE for 24h compliance
                    # Template Name: daily_rashiphalalu_v1
                    # Variables: [message_body]
                    msg_id = await self.whatsapp.send_template_message(
                        phone=user.phone,
                        template_name="daily_rashiphalalu_v1",
                        components=[{
                            "type": "body",
                            "parameters": [{"type": "text", "text": message}]
                        }]
                    )
                    if msg_id:
                        # Increment the days counter for 6-day eligibility
                        user.rashiphalalu_days_sent += 1
                        sent += 1
                        logger.debug(f"Sent to {user.phone}, days_sent={user.rashiphalalu_days_sent}")
            except Exception as e:
                logger.error(f"Failed to send to {user.phone}: {e}")
        
        # Commit all changes
        await self.db.flush()
        
        logger.info(f"Broadcast complete: {sent} personalized messages sent")
        return sent
    
    async def get_message_for_user(self, user: User, target_date: Optional[date] = None) -> Optional[str]:
        """Get the personalized Rashiphalalu message for a specific user."""
        return await self.generate_personalized_message(user, target_date)
    
    async def _generate_for_rashi(self, target_date: date, rashi: Rashi) -> Optional[str]:
        """Generate Rashiphalalu for a specific rashi (cached version)."""
        if not client:
            logger.error("OpenAI client not configured")
            return None
        
        # Get panchang
        panchang = await self.panchang.get_panchang(target_date)
        date_telugu = self._format_date_telugu(target_date)
        
        user_prompt = f"""ఈ రోజు వివరాలు:
- తేది: {date_telugu}
- వారం: {panchang.vara_telugu}
- తిథి: {panchang.tithi_telugu}
- పక్షం: {panchang.paksha}
- నక్షత్రం: {panchang.nakshatra_telugu}

రాశి: {rashi.value} ({rashi.telugu_name})

దయచేసి ఈ రాశికి సమగ్ర ఫలం రాయండి (3-4 వాక్యాలు). 
పూర్తిగా తెలుగులో రాయండి. ఆంగ్ల లిపి వాడవద్దు. 
ఆశావహంగా, ధైర్యం ఇచ్చేలా ఉండాలి."""

        try:
            response = await client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=200,
                temperature=0.7,
            )
            
            message = response.choices[0].message.content.strip()
            logger.debug(f"Generated for {rashi.value}: {message[:50]}...")
            return message
            
        except Exception as e:
            logger.error(f"OpenAI generation failed for {rashi.value}: {e}")
            return None
    
    async def _get_cached_message(self, target_date: date, rashi: str) -> Optional[str]:
        """Get cached message from database."""
        result = await self.db.execute(
            select(RashiphalaluCache)
            .where(RashiphalaluCache.date == target_date)
            .where(RashiphalaluCache.rashi == rashi)
            .where(RashiphalaluCache.language_variant == "te")
        )
        cache = result.scalar_one_or_none()
        return cache.message_text if cache else None
    
    async def _get_active_users(self) -> List[User]:
        """Get all active users with rashi set."""
        from app.fsm.states import ConversationState
        
        result = await self.db.execute(
            select(User)
            .where(User.rashi.isnot(None))
            .where(User.state.not_in([
                ConversationState.NEW.value,
                ConversationState.WAITING_FOR_RASHI.value,
                ConversationState.WAITING_FOR_DEITY.value,
                ConversationState.WAITING_FOR_AUSPICIOUS_DAY.value,
            ]))
        )
        return list(result.scalars().all())
    
    async def _get_users_by_rashi(self, rashi: str) -> List[User]:
        """Get all active users with a specific rashi."""
        from app.fsm.states import ConversationState
        
        result = await self.db.execute(
            select(User)
            .where(User.rashi == rashi)
            .where(User.state.not_in([
                ConversationState.NEW.value,
                ConversationState.WAITING_FOR_RASHI.value,
                ConversationState.WAITING_FOR_DEITY.value,
                ConversationState.WAITING_FOR_AUSPICIOUS_DAY.value,
            ]))
        )
        return list(result.scalars().all())

    async def send_daily_rashi_to_user(self, user: User, target_date: Optional[date] = None) -> bool:
        """Send daily rashiphalalu to a specific user using templates."""
        if not target_date:
            from datetime import datetime, timezone
            target_date = datetime.now(timezone.utc).date()
            
        message = await self.generate_personalized_message(user, target_date)
        
        if message:
            # Using template for 24h compliance + automated delivery
            msg_id = await self.whatsapp.send_template_message(
                phone=user.phone,
                template_name="daily_rashiphalalu_v1",
                components=[{
                    "type": "body",
                    "parameters": [{"type": "text", "text": message}]
                }]
            )
            return bool(msg_id)
        return False
