"""
FSM State Definitions.
All conversation states and enums as per the Engineering Spec.
"""

from enum import Enum


class ConversationState(str, Enum):
    """
    All possible conversation states.
    Strict transition rules - only one valid next state per input type.
    """
    
    # Onboarding states
    NEW = "NEW"
    WAITING_FOR_RASHI = "WAITING_FOR_RASHI"
    WAITING_FOR_NAKSHATRA = "WAITING_FOR_NAKSHATRA"  # Optional
    WAITING_FOR_BIRTH_TIME = "WAITING_FOR_BIRTH_TIME"  # Optional
    WAITING_FOR_DEITY = "WAITING_FOR_DEITY"
    WAITING_FOR_AUSPICIOUS_DAY = "WAITING_FOR_AUSPICIOUS_DAY"
    ONBOARDED = "ONBOARDED"
    
    # Daily passive state
    DAILY_PASSIVE = "DAILY_PASSIVE"
    
    # Weekly sankalp flow states
    WEEKLY_PROMPT_SENT = "WEEKLY_PROMPT_SENT"
    WAITING_FOR_CATEGORY = "WAITING_FOR_CATEGORY"
    WAITING_FOR_TIER = "WAITING_FOR_TIER"
    PAYMENT_LINK_SENT = "PAYMENT_LINK_SENT"
    PAYMENT_CONFIRMED = "PAYMENT_CONFIRMED"
    RECEIPT_SENT = "RECEIPT_SENT"
    
    # Cooldown state (post-payment)
    COOLDOWN = "COOLDOWN"


class SankalpCategory(str, Enum):
    """
    Sankalp categories - user must pick exactly one.
    Button payloads use these values.
    """
    
    FAMILY = "CAT_FAMILY"           # Pillalu / Parivaaram
    HEALTH = "CAT_HEALTH"           # Arogyam / Raksha
    CAREER = "CAT_CAREER"           # Udyogam / Arthika Chinta
    PEACE = "CAT_PEACE"             # Manasika Shanti
    
    @property
    def display_name_telugu(self) -> str:
        """Telugu display name for the category."""
        names = {
            self.FAMILY: "పిల్లలు / పరివారం",
            self.HEALTH: "ఆరోగ్యం / రక్ష",
            self.CAREER: "ఉద్యోగం / ఆర్థిక చింత",
            self.PEACE: "మానసిక శాంతి",
        }
        return names.get(self, self.value)
    
    @property
    def display_name_english(self) -> str:
        """English display name for the category."""
        names = {
            self.FAMILY: "Children / Family",
            self.HEALTH: "Health / Protection",
            self.CAREER: "Career / Financial",
            self.PEACE: "Mental Peace",
        }
        return names.get(self, self.value)


class SankalpTier(str, Enum):
    """
    Sankalp pricing tiers.
    Button payloads use these values.
    """
    
    S15 = "TIER_S15"    # $15 - Samuhik Sankalp
    S30 = "TIER_S30"    # $30 - Vishesh Sankalp
    S50 = "TIER_S50"    # $50 - Parivaar Sankalp
    
    @property
    def amount_usd(self) -> int:
        """Amount in USD cents."""
        amounts = {
            self.S15: 1500,
            self.S30: 3000,
            self.S50: 5000,
        }
        return amounts.get(self, 0)
    
    @property
    def display_name(self) -> str:
        """Display name for the tier."""
        names = {
            self.S15: "$15 - Samuhik Sankalp",
            self.S30: "$30 - Vishesh Sankalp",
            self.S50: "$50 - Parivaar Sankalp",
        }
        return names.get(self, self.value)


class SankalpStatus(str, Enum):
    """Status of a sankalp record."""
    
    INITIATED = "INITIATED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    RECEIPT_SENT = "RECEIPT_SENT"
    CLOSED = "CLOSED"


class Rashi(str, Enum):
    """
    12 Rashis (Zodiac signs) in Telugu.
    Used for daily Rashiphalalu personalization.
    """
    
    MESHA = "MESHA"         # Aries - మేషం
    VRISHABHA = "VRISHABHA" # Taurus - వృషభం
    MITHUNA = "MITHUNA"     # Gemini - మిథునం
    KARKATAKA = "KARKATAKA" # Cancer - కర్కాటకం
    SIMHA = "SIMHA"         # Leo - సింహం
    KANYA = "KANYA"         # Virgo - కన్య
    TULA = "TULA"           # Libra - తుల
    VRISHCHIKA = "VRISHCHIKA" # Scorpio - వృశ్చికం
    DHANU = "DHANU"         # Sagittarius - ధనుస్సు
    MAKARA = "MAKARA"       # Capricorn - మకరం
    KUMBHA = "KUMBHA"       # Aquarius - కుంభం
    MEENA = "MEENA"         # Pisces - మీనం
    
    @property
    def telugu_name(self) -> str:
        """Telugu name for the rashi."""
        names = {
            self.MESHA: "మేషం",
            self.VRISHABHA: "వృషభం",
            self.MITHUNA: "మిథునం",
            self.KARKATAKA: "కర్కాటకం",
            self.SIMHA: "సింహం",
            self.KANYA: "కన్య",
            self.TULA: "తుల",
            self.VRISHCHIKA: "వృశ్చికం",
            self.DHANU: "ధనుస్సు",
            self.MAKARA: "మకరం",
            self.KUMBHA: "కుంభం",
            self.MEENA: "మీనం",
        }
        return names.get(self, self.value)


class AuspiciousDay(str, Enum):
    """
    Days of the week for auspicious day preference.
    Each day is associated with specific deities.
    """
    
    SUNDAY = "SUNDAY"       # Aadivaram - Surya
    MONDAY = "MONDAY"       # Somavaram - Shiva
    TUESDAY = "TUESDAY"     # Mangalavaram - Hanuman/Kartikeya
    WEDNESDAY = "WEDNESDAY" # Budhavaram - Vishnu
    THURSDAY = "THURSDAY"   # Guruvaram - Vishnu/Guru
    FRIDAY = "FRIDAY"       # Shukravaram - Lakshmi/Durga
    SATURDAY = "SATURDAY"   # Shanivaram - Shani/Hanuman
    
    @property
    def telugu_name(self) -> str:
        """Telugu name for the day."""
        names = {
            self.SUNDAY: "ఆదివారం",
            self.MONDAY: "సోమవారం",
            self.TUESDAY: "మంగళవారం",
            self.WEDNESDAY: "బుధవారం",
            self.THURSDAY: "గురువారం",
            self.FRIDAY: "శుక్రవారం",
            self.SATURDAY: "శనివారం",
        }
        return names.get(self, self.value)


class Deity(str, Enum):
    """
    Preferred deity for sankalp offerings.
    """
    
    SHIVA = "SHIVA"
    VISHNU = "VISHNU"
    HANUMAN = "HANUMAN"
    LAKSHMI = "LAKSHMI"
    DURGA = "DURGA"
    GANESHA = "GANESHA"
    VENKATESHWARA = "VENKATESHWARA"
    SAIBABA = "SAIBABA"
    
    @property
    def telugu_name(self) -> str:
        """Telugu name for the deity."""
        names = {
            self.SHIVA: "శివుడు",
            self.VISHNU: "విష్ణువు",
            self.HANUMAN: "హనుమాన్",
            self.LAKSHMI: "లక్ష్మీ దేవి",
            self.DURGA: "దుర్గా దేవి",
            self.GANESHA: "గణపతి",
            self.VENKATESHWARA: "వేంకటేశ్వరుడు",
            self.SAIBABA: "సాయిబాబా",
        }
        return names.get(self, self.value)


class Nakshatra(str, Enum):
    """
    27 Nakshatras (birth stars) in Telugu.
    Optional during onboarding for more personalized content.
    """
    
    ASHWINI = "ASHWINI"           # అశ్విని
    BHARANI = "BHARANI"           # భరణి
    KRITTIKA = "KRITTIKA"         # కృత్తిక
    ROHINI = "ROHINI"             # రోహిణి
    MRIGASHIRA = "MRIGASHIRA"     # మృగశిర
    ARDRA = "ARDRA"               # ఆర్ద్ర
    PUNARVASU = "PUNARVASU"       # పునర్వసు
    PUSHYA = "PUSHYA"             # పుష్యమి
    ASHLESHA = "ASHLESHA"         # ఆశ్లేష
    MAGHA = "MAGHA"               # మఘ
    PURVAPHALGUNI = "PURVAPHALGUNI"   # పూర్వఫల్గుణి
    UTTARAPHALGUNI = "UTTARAPHALGUNI" # ఉత్తరఫల్గుణి
    HASTA = "HASTA"               # హస్త
    CHITRA = "CHITRA"             # చిత్ర
    SWATI = "SWATI"               # స్వాతి
    VISHAKHA = "VISHAKHA"         # విశాఖ
    ANURADHA = "ANURADHA"         # అనురాధ
    JYESHTHA = "JYESHTHA"         # జ్యేష్ఠ
    MOOLA = "MOOLA"               # మూల
    PURVASHADHA = "PURVASHADHA"   # పూర్వాషాఢ
    UTTARASHADHA = "UTTARASHADHA" # ఉత్తరాషాఢ
    SHRAVANA = "SHRAVANA"         # శ్రవణం
    DHANISHTA = "DHANISHTA"       # ధనిష్ఠ
    SHATABHISHA = "SHATABHISHA"   # శతభిషం
    PURVABHADRA = "PURVABHADRA"   # పూర్వాభాద్ర
    UTTARABHADRA = "UTTARABHADRA" # ఉత్తరాభాద్ర
    REVATI = "REVATI"             # రేవతి
    
    @property
    def telugu_name(self) -> str:
        """Telugu name for the nakshatra."""
        names = {
            self.ASHWINI: "అశ్విని",
            self.BHARANI: "భరణి",
            self.KRITTIKA: "కృత్తిక",
            self.ROHINI: "రోహిణి",
            self.MRIGASHIRA: "మృగశిర",
            self.ARDRA: "ఆర్ద్ర",
            self.PUNARVASU: "పునర్వసు",
            self.PUSHYA: "పుష్యమి",
            self.ASHLESHA: "ఆశ్లేష",
            self.MAGHA: "మఘ",
            self.PURVAPHALGUNI: "పూర్వఫల్గుణి",
            self.UTTARAPHALGUNI: "ఉత్తరఫల్గుణి",
            self.HASTA: "హస్త",
            self.CHITRA: "చిత్ర",
            self.SWATI: "స్వాతి",
            self.VISHAKHA: "విశాఖ",
            self.ANURADHA: "అనురాధ",
            self.JYESHTHA: "జ్యేష్ఠ",
            self.MOOLA: "మూల",
            self.PURVASHADHA: "పూర్వాషాఢ",
            self.UTTARASHADHA: "ఉత్తరాషాఢ",
            self.SHRAVANA: "శ్రవణం",
            self.DHANISHTA: "ధనిష్ఠ",
            self.SHATABHISHA: "శతభిషం",
            self.PURVABHADRA: "పూర్వాభాద్ర",
            self.UTTARABHADRA: "ఉత్తరాభాద్ర",
            self.REVATI: "రేవతి",
        }
        return names.get(self, self.value)
