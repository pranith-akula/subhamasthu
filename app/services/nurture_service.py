
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import joinedload

from app.models.user import User
from app.models.sankalp import Sankalp, SankalpStatus
from app.models.message_log import MessageLog, MessageType, MessageStatus
from app.services.meta_whatsapp_service import MetaWhatsappService
from app.config import settings

logger = logging.getLogger(__name__)

class NurtureService:
    """
    Service to handle the 28-Day Trust Engine cycle.
    - Manages 3 Tracks: DEVOTION, FAMILY (SECURITY), CAREER (GROWTH).
    - Sends daily content based on user.nurture_day.
    - Handles Surprise Days and Sankalp Invites.
    """
    
    # 28-Day Content Map
    # Structure: {day: {track: {type, content}}}
    # Use placeholders for now.
    # 28-Day Theme Map for Dynamic Generation
    # 28-Day Theme Library (Sacred Calendar)
    # Structure: {cycle_number: {week_number: { emotional_goal, anchor }}}
    THEME_LIBRARY = {
        1: { # Cycle 1: Temple Journey (Grounding)
            1: {"goal": "Connection & Grounding", "anchor": "Tirumala (Venkateswara Swamy) - Deep Trust & Faith"},
            2: {"goal": "Story & Wisdom", "anchor": "Annavaram (Satyanarayana Swamy) - Patience & Truth"},
            3: {"goal": "Practice & Grace", "anchor": "Simhachalam (Narasimha Swamy) - Courage & Protection"},
            4: {"goal": "Commitment", "anchor": "Srisailam (Mallikarjuna Swamy) - Stability & Cosmic Connection"},
        },
        2: { # Cycle 2: Bhagavatam Tales (Inspiration)
            1: {"goal": "Identity & Devotion", "anchor": "Prahlada Charitra - The omnipresence of Divine in every atom"},
            2: {"goal": "Grace in Crisis", "anchor": "Gajendra Moksham - Total surrender and timely rescue"},
            3: {"goal": "Focus & Resolve", "anchor": "Dhruva Charitra - Unwavering focus on spiritual goals"},
            4: {"goal": "Divine Play/Community", "anchor": "Krishna Leela - Finding joy and safety in the Divine community"},
        },
        3: { # Cycle 3: Saint-Poets (Emotion)
            1: {"goal": "Soulful Connection", "anchor": "Annamayya - Seeing the Divine in every aspect of life (Adigo Alladigo)"},
            2: {"goal": "Resilience in Bondage", "anchor": "Bhakta Ramadasu - Faith even in the darkest prison (Bhadradri Ramudu)"},
            3: {"goal": "Pure Devotion", "anchor": "Tyagaraja - The power of Rama-Namam and musical prayer"},
            4: {"goal": "Humility & Service", "anchor": "Bammera Potana - The joy of selfless creation and spiritual depth"},
        },
        4: { # Cycle 4: Dharma Sathakams (Wisdom)
            1: {"goal": "Ethics & Roots", "anchor": "Sumathi Sathakam - Living with dignity and traditional values"},
            2: {"goal": "Worldly Wisdom", "anchor": "Vemana Sathakam - Deep truths in simple observations"},
            3: {"goal": "Character & Strength", "anchor": "Bhartruhari Subhashitalu - Strengthening the inner self"},
            4: {"goal": "Cycles of Life", "anchor": "Kalachakra & Dharma - Understanding the flow of time and duty"},
        }
    }

    # Technical Theme Map for LLM guidance
    THEME_MAP = {
        1: "Welcome & Identity: Affirm they made a good choice.",
        2: "Proof of Impact: Describe the specific impact of Annadanam.",
        3: "Wisdom: A short, deep quote relevant to their track.",
        4: "Application: A small, easy spiritual practice for today.",
        5: "Impact: A story of a beneficiary or temple helped.",
        6: "Preparation: Preparing the mind for the upcoming Sankalp.",
        7: "INVITE: Weekly Sankalp Invitation.",
        17: "COLLECTIVE PRAYER: Community feeling.",
        28: "INVITE: Monthly Maha Sankalp Invitation.",
    }
    
    SYSTEM_PROMPT = """You are a warm, wise, and spiritual guide for 'Subhamasthu', a Vedic community.
    Your goal is to nurture the user based on their specific 'Track' and the daily 'Theme'.
    
    IMPORTANT: You MUST write the entire message in PURE TELUGU (Telugu script). 
    Use a 'Matriarchal-Respectful' (Gaurava) tone suitable for NRI Telugu families.
    Avoid English words entirely. Use spiritual and traditional vocabulary.
    
    Tracks:
    - DEVOTION (భక్తి మర్గం): Focus on Bhakti, peace, connection to God.
    - SECURITY (కుటుంబ క్షేమం): Focus on family protection, health, safety, ancestors.
    - GROWTH (అభ్యుదయం): Focus on career, overcoming obstacles, success, focus.
    
    Guidelines:
    - Keep it short (2-3 sentences max). WhatsApp friendly.
    - Day-specific themes will be provided. Incorporate the month's 'Sacred Anchor' naturally.
    - For 'INVITE' days, include a spiritual reason why they should participate.
    - NO generic 'Namaste'. Use traditional greetings like 'ఓం నమో నారాయణాయ' or 'శుభమస్తు'.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.whatsapp = MetaWhatsappService()
        self.openai_client = None
        if settings.openai_api_key:
             from openai import AsyncOpenAI
             self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def _get_content(self, day: int, track: str, cycle: int = 1, user_name: str = "భక్తులు") -> Optional[Dict]:
        """Generate content dynamically via LLM, aware of cycle and week."""
        base_theme = self.THEME_MAP.get(day) or "Daily spiritual guidance and reflection."
        
        # Determine week for Anchor selection
        week = ((day - 1) // 7) + 1
        cycle_data = self.THEME_LIBRARY.get(cycle, self.THEME_LIBRARY[1])
        week_data = cycle_data.get(week, cycle_data[1])
        
        emotional_goal = week_data["goal"]
        anchor = week_data["anchor"]
        
        # Hardcoded types for structure
        msg_type = "text"
        if day in [7, 28]:
            msg_type = "sankalp_invite"
            
        if not self.openai_client:
            logger.warning("OpenAI client not initialized, using fallback.")
            return {"type": "text", "body": f"ఓం నమో నారాయణాయ {user_name}. నేడు మీ ఆధ్యాత్మిక పయనంలో {day}వ రోజు."}

        try:
            prompt = f"""
            User Name: {user_name}
            Track: {track}
            Day (Month Day): {day}
            Month (Cycle): {cycle}
            Week of Cycle: {week}
            Emotional Goal of the week: {emotional_goal}
            Monthly Sacred Anchor: {anchor}
            Daily Theme Instruction: {base_theme}
            
            Write the message body in Pure Telugu script. Focus on the emotional goal and the sacred anchor.
            """
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=250,
                temperature=0.7
            )
            
            body = response.choices[0].message.content.strip()
            body = body.replace('"', '').replace("'", "")
            
            if msg_type == "sankalp_invite":
                 return {
                     "type": "sankalp_invite", 
                     "body": body,
                     "buttons": ["Dharmika (₹1750)", "Punya Vriddhi (₹4200)", "Maha Sankalp (₹8900)"]
                 }
                 
            return {"type": "text", "body": body}

        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            return {"type": "text", "body": f"శుభమస్తు {user_name}! నేటి మీ దైవిక ప్రయాణం శాంతియుతంగా సాగాలని కోరుకుంటున్నాము."}

    async def process_nurture_for_user(self, user: User) -> bool:
        """
        Process the daily nurture step for a single user.
        Called by the Hourly Worker when next_nurture_at <= Now.
        """
        try:
            now_utc = datetime.now(timezone.utc)
            idempotency_key = f"nurture_{now_utc.date()}_{user.id}"
            
            # 0. Idempotency Check (Strategic Opt)
            query = select(MessageLog).where(MessageLog.idempotency_key == idempotency_key)
            result = await self.db.execute(query)
            if result.scalar_one_or_none():
                logger.warning(f"Skipping duplicate nurture for {user.phone}: {idempotency_key}")
                return True

            logger.info(f"Processing nurture for user {user.phone}, Day {user.nurture_day}, Track {user.nurture_track}")
            
            # 1. Get Content
            cycle = getattr(user, 'devotional_cycle_number', 1) or 1
            content = await self._get_content(user.nurture_day, user.nurture_track, cycle, user.name or "భక్తులు")
            
            # 2. Check Logic (Sankalp Invite vs Rest)
            if user.nurture_day in [7, 28]: # Week 1 & 4 Sundays
                 if self._should_send_invite(user):
                     await self._send_sankalp_invite(user, content)
                 else:
                     await self._send_rest_message(user)
            elif user.nurture_day == user.surprise_day:
                 await self._send_surprise_blessing(user)
            elif content:
                 await self._send_content(user, content)
            
            # 3. Log Success
            msg_log = MessageLog(
                user_id=user.id,
                message_type=MessageType.NURTURE,
                content_preview=str(content.get("type", "unknown")),
                status=MessageStatus.SENT,
                idempotency_key=idempotency_key
            )
            self.db.add(msg_log)
            
            # 4. Advance State
            await self._advance_user_state(user)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to process nurture for {user.phone}: {e}", exc_info=True)
            return False


    def _should_send_invite(self, user: User) -> bool:
        """Check safeguards."""
        # Anti-predatory: Max 2 sankalps in 28-day cycle
        if user.sankalps_in_cycle >= 2:
            return False
        return True

    async def _send_content(self, user: User, content: Dict):
        """Send message via WhatsApp."""
        if content["type"] == "text":
            await self.whatsapp.send_text_message(user.phone, content["body"])
        elif content["type"] == "image":
             # Need media ID or URL
             pass 

    async def _send_sankalp_invite(self, user: User, content: Dict):
        """Send soft invite."""
        logger.info(f"Sending Sankalp Invite to {user.phone}")
        
        buttons_data = []
        for btn_label in content.get("buttons", ["$21 (Dharmika)", "$51 (Punya Vriddhi)", "$108 (Maha Sankalp)"]):
             # Extract amount for ID? e.g. "sankalp_21"
             # Assuming label is like "$21 (Archana)" or just "$21"
             clean_label = btn_label.split(" ")[0].replace("$", "").replace("₹", "")
             buttons_data.append({
                 "id": f"sankalp_invite_{clean_label}",
                 "title": btn_label[:20] # Max 20 chars
             })
             
        await self.whatsapp.send_button_message(
            phone=user.phone,
            body_text=content["body"],
            buttons=buttons_data
        )

    async def _send_rest_message(self, user: User):
        """Send rest/blessing message."""
        await self.whatsapp.send_text_message(user.phone, "ఓం శాంతి. ఈ ఆదివారం పరమాత్ముని చింతనలో ప్రశాంతంగా గడపండి.")

    async def _send_surprise_blessing(self, user: User):
        """Send surprise."""
        await self.whatsapp.send_text_message(user.phone, "శుభవార్త! నేడు మీ పేరు మీద ఆలయంలో ప్రత్యేక అర్చన జరిపించబడింది. ధర్మం మిమ్మల్ని ఎల్లప్పుడూ రక్షిస్తుంది. 🙏")

    async def _advance_user_state(self, user: User):
        """Update DB timestamps and counters."""
        # Increment day
        user.nurture_day += 1
        if user.nurture_day > 28:
            user.nurture_day = 1
            user.sankalps_in_cycle = 0 # Reset cycle counter
            
            # Increment Devotional Cycle (Max 4)
            current_cycle = getattr(user, 'devotional_cycle_number', 1) or 1
            if current_cycle < 4:
                user.devotional_cycle_number = current_cycle + 1
                logger.info(f"User {user.phone} advanced to Devotional Cycle {user.devotional_cycle_number}")
            
            import random
            user.surprise_day = random.randint(14, 20) # New surprise day
            
        # Update next_nurture_at (Add 24 hours to PREVIOUS schedule to maintain time)
        # Or recalculate from TZ? Safer to add 24h if schedule was correct.
        if user.next_nurture_at:
             user.next_nurture_at += timedelta(days=1)
        else:
             # Fallback
             pass
             
        user.last_nurture_sent_at = datetime.now(timezone.utc)
        
        await self.db.flush() # Caller commits
