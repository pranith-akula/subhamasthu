"""
Personalization Service - GPT-powered personalized content generation.

All user-facing messages are personalized based on:
- Rashi (zodiac sign)
- Nakshatra (birth star)
- Preferred Deity
- Today's Panchang (tithi, nakshatra, vara)
- Context (category, situation)
"""

import logging
from datetime import date
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.services.panchang_service import PanchangService

logger = logging.getLogger(__name__)


# Telugu mappings for consistency
RASHI_TELUGU = {
    "mesha": "మేషం", "vrishabha": "వృషభం", "mithuna": "మిథునం",
    "karkataka": "కర్కాటకం", "simha": "సింహం", "kanya": "కన్య",
    "tula": "తుల", "vrishchika": "వృశ్చికం", "dhanu": "ధనుస్సు",
    "makara": "మకరం", "kumbha": "కుంభం", "meena": "మీనం",
}

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
    "ayyappa": "అయ్యప్ప స్వామి",
    "subrahmanya": "సుబ్రహ్మణ్య స్వామి",
    "other": "భగవంతుడు",
}

CATEGORY_TELUGU = {
    "CAT_FAMILY": "పిల్లలు / పరివారం",
    "CAT_HEALTH": "ఆరోగ్యం / రక్ష",
    "CAT_CAREER": "ఉద్యోగం / ఆర్థికం",
    "CAT_PEACE": "మానసిక శాంతి",
}


class PersonalizationService:
    """
    Service for generating personalized content via GPT.
    
    All content is generated in Pure Telugu with a formal, temple-like tone.
    """
    
    SYSTEM_PROMPT = """నీవు అనుభవజ్ఞుడైన వేద పండితుడివి. తెలుగు కుటుంబాలకు ఆధ్యాత్మిక మార్గదర్శనం అందించే పవిత్ర బాధ్యత నీది.

నీ సందేశాలు:
- పూర్తిగా తెలుగులో ఉండాలి (ఏ ఆంగ్లం వద్దు, english script వాడకూడదు).
- ఇంగ్లీష్ లిపిలో తెలుగు రాయకూడదు (Do not use English script for Telugu words).
- ఆశావహంగా, ధైర్యం కలిగించేలా ఉండాలి
- భయం, ఆందోళన కలిగించకూడదు
- వేద/పురాణ ఆధారంగా ఉండాలి
- సరళంగా, అందరికీ అర్థమయ్యేలా ఉండాలి
- WhatsApp కు తగినట్లు క్లుప్తంగా ఉండాలి (50-100 పదాలు)

వినియోగదారు వివరాల ఆధారంగా వ్యక్తిగతీకరించు:
- వారి రాశి ప్రకారం సూచనలు ఇవ్వు
- వారి నక్షత్రానికి తగిన మంత్రాలు సూచించు
- వారి ఇష్ట దైవం ఆధారంగా పరిహారాలు చెప్పు

శైలి: పండితుని వలె హుందాగా, కానీ స్నేహపూర్వకంగా.
స్వరం: ఆశ్వాసన > భయం, ధైర్యం > నిరాశ."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.panchang = PanchangService()
    
    @property
    def model(self) -> str:
        return settings.openai_model or "gpt-4o-mini"
    
    def _get_user_context(self, user: User) -> dict:
        """Build user context for GPT prompts."""
        rashi = getattr(user, 'rashi', 'mesha') or 'mesha'
        nakshatra = getattr(user, 'nakshatra', None)
        deity = getattr(user, 'preferred_deity', 'other') or 'other'
        name = user.name or "భక్తులు"
        
        return {
            "name": name,
            "rashi": rashi,
            "rashi_telugu": RASHI_TELUGU.get(rashi.lower(), "మేషం"),
            "nakshatra": nakshatra,
            "deity": deity,
            "deity_telugu": DEITY_TELUGU.get(deity, "భగవంతుడు"),
        }
    
    async def _get_panchang_context(self, target_date: Optional[date] = None) -> dict:
        """Get today's Panchang for context."""
        target_date = target_date or date.today()
        panchang = self.panchang.get_panchang(target_date)
        
        return {
            "date": target_date.isoformat(),
            "vara": panchang.vara_telugu,
            "tithi": panchang.tithi_telugu,
            "nakshatra": panchang.nakshatra_telugu,
            "paksha": panchang.paksha,
        }
    
    async def generate_pariharam(
        self,
        user: User,
        category: str,
        target_date: Optional[date] = None,
    ) -> str:
        """
        Generate personalized Pariharam - 3-Day Ritual Journey.
        """
        user_ctx = self._get_user_context(user)
        panchang_ctx = await self._get_panchang_context(target_date)
        category_telugu = CATEGORY_TELUGU.get(category, category)
        
        prompt = f"""వినియోగదారు వివరాలు:
- పేరు: {user_ctx['name']}
- రాశి: {user_ctx['rashi_telugu']}
- నక్షత్రం: {user_ctx['nakshatra'] or 'తెలియదు'}
- ఇష్ట దైవం: {user_ctx['deity_telugu']}

ఈ రోజు పంచాంగం:
- వారం: {panchang_ctx['vara']}
- తిథి: {panchang_ctx['tithi']}

సమస్య: {category_telugu}

ఈ వ్యక్తికి 3 రోజుల చిన్న ఆధ్యాత్మిక సాధన (Micro-Ritual) సూచించు.

ఫార్మాట్ (ఖచ్చితంగా ఇలాగే ఉండాలి):
రోజు 1 (మంత్రం): [వారి ఇష్ట దైవానికి సంబంధించిన చిన్న మంత్రం]
రోజు 2 (క్రియ): [ఒక చిన్న పని - ఉదా: నీరు పోయడం, దీపం, దానం]
రోజు 3 (నియమం): [ఒక మానసిక మార్పు - ఉదా: కోపం తగ్గించుకోవడం, మౌనం]

పూర్తిగా తెలుగులో ఉండాలి."""

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=250,
                temperature=0.7,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Pariharam generation failed: {e}")
            return "రోజు 1: ఓం నమో నారాయణాయ జపం\nరోజు 2: పక్షులకు నీరు పెట్టండి\nరోజు 3: కోపం తగ్గించుకోండి"

    async def generate_sankalp_statement(
        self,
        user: User,
        category: str,
        target_date: Optional[date] = None,
    ) -> str:
        """
        Generate personalized Sankalp statement with Cosmic Context.
        """
        user_ctx = self._get_user_context(user)
        panchang_ctx = await self._get_panchang_context(target_date)
        category_telugu = CATEGORY_TELUGU.get(category, category)
        
        # Generate Sankalp ID
        import random
        sid = f"SV-{date.today().year}-{date.today().month:02d}-{random.randint(100,999)}"
        
        prompt = f"""వినియోగదారు వివరాలు:
- పేరు: {user_ctx['name']}
- రాశి: {user_ctx['rashi_telugu']}
- నక్షత్రం: {user_ctx['nakshatra'] or 'తెలియదు'}
- ఇష్ట దైవం: {user_ctx['deity_telugu']}

కాస్మిక్ సందర్భం (Cosmic Context):
- తిథి: {panchang_ctx['tithi']}
- వారం: {panchang_ctx['vara']}
- నక్షత్రం: {panchang_ctx['nakshatra']}

సంకల్పం ఆశయం: {category_telugu} (భారం తొలగిపోవాలి)
Sankalp ID: {sid}

ఈ వివరాలతో ఒక పవిత్రమైన సంకల్పాన్ని రాయి.
ఇందులో తప్పకుండా ఉండాల్సినవి:
1. "నేను, [పేరు]..." అని మొదలుపెట్టాలి.
2. తిథి, నక్షత్రం ప్రస్తావన ఉండాలి ("ఈ శుభ సమయంలో...").
3. వారి సమస్య ({category_telugu}) భగవంతుని పాదాల చెంత విడుస్తున్నట్లు ఉండాలి.
4. చివర్లో "Sankalp ID: {sid}" అని ఉండాలి.

చాల పవిత్రంగా, బలంగా ఉండాలి."""

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=250,
                temperature=0.7,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Sankalp generation failed: {e}")
            return f"నేను, {user_ctx['name']}, ఈ రోజు భగవంతుని సాక్షిగా నా సంకల్పాన్ని తీసుకుంటున్నాను. \n\nSankalp ID: {sid}"
    
    async def generate_chinta_prompt(
        self,
        user: User,
        target_date: Optional[date] = None,
    ) -> str:
        """
        Generate personalized Chinta (concern) prompt for auspicious day.
        """
        user_ctx = self._get_user_context(user)
        panchang_ctx = await self._get_panchang_context(target_date)
        
        prompt = f"""వినియోగదారు వివరాలు:
- పేరు: {user_ctx['name']}
- రాశి: {user_ctx['rashi_telugu']}
- ఇష్ట దైవం: {user_ctx['deity_telugu']}

ఈ రోజు పంచాంగం:
- వారం: {panchang_ctx['vara']}
- తిథి: {panchang_ctx['tithi']}

ఈ వ్యక్తికి వారి శుభ దినం (ఇష్ట దైవం రోజు) నాడు పంపే సందేశం రాయి.

సందేశంలో:
1. శుభ వారం అభినందన
2. ఇష్ట దైవం కృప గురించి
3. మనసులో చింత ఉందా అని అడగడం

స్వరం: స్నేహపూర్వకంగా, ఆశావహంగా.
పొడవు: 3-4 వాక్యాలు మాత్రమే.
పూర్తిగా తెలుగులో రాయండి (ఆంగ్ల లిపి వద్దు)."""

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=120,
                temperature=0.7,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Chinta prompt generation failed: {e}")
            # Fallback
            return f"🙏 శుభ {panchang_ctx['vara']}! ఈ రోజు {user_ctx['deity_telugu']} కృప మీపై ఉంది. మీ మనసులో ఏమి చింత ఉంది?"
    
    async def generate_punya_confirmation(
        self,
        user: User,
        category: str,
        pariharam: str,
        families_fed: int,
        amount: float,
        target_date: Optional[date] = None,
    ) -> str:
        """
        Generate personalized Punya (merit) confirmation message.
        """
        user_ctx = self._get_user_context(user)
        panchang_ctx = await self._get_panchang_context(target_date)
        category_telugu = CATEGORY_TELUGU.get(category, category)
        
        prompt = f"""వినియోగదారు వివరాలు:
- పేరు: {user_ctx['name']}
- రాశి: {user_ctx['rashi_telugu']}
- ఇష్ట దైవం: {user_ctx['deity_telugu']}

సంకల్ప వివరాలు:
- విభాగం: {category_telugu}
- పరిహారం: {pariharam}
- త్యాగం: ${amount}
- అన్నదానం: {families_fed} కుటుంబాలకు

ఈ వ్యక్తికి సంకల్ప పూర్తి సందేశం రాయి.

సందేశంలో:
1. త్యాగం స్వీకరించబడింది అని
2. పరిహారం గుర్తుంచుకోమని
3. 7 రోజులు శాంతిగా ఉండమని
4. ఇష్ట దైవం తోడుగా ఉన్నారని

స్వరం: ఆశీర్వాద స్వరంలో, ఆధ్యాత్మికంగా.
పొడవు: 5-6 వాక్యాలు.
పూర్తిగా తెలుగులో రాయండి (ఆంగ్ల లిపి వద్దు)."""

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=200,
                temperature=0.7,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Punya confirmation generation failed: {e}")
            # Fallback
            return f"🙏 {user_ctx['name']} గారు, మీ సంకల్పం {user_ctx['deity_telugu']} సన్నిధిలో అర్పించబడింది. మీ ${amount} త్యాగం ద్వారా {families_fed} కుటుంబాలకు అన్నదానం జరుగుతుంది. 7 రోజులు శాంతిగా ఉండండి. ఓం శాంతి 🙏"
