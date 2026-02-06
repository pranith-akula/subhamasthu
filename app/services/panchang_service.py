"""
Panchang Service - Hindu calendar data for Rashiphalalu generation.
Provides Tithi, Nakshatra, Vara, and other Vedic astrology elements.
"""

import logging
from datetime import date, datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PanchangData:
    """Daily Panchang information."""
    date: date
    
    # Vara (Day)
    vara_english: str
    vara_telugu: str
    
    # Tithi
    tithi_name: str
    tithi_telugu: str
    paksha: str  # శుక్ల or కృష్ణ
    
    # Nakshatra
    nakshatra_name: str
    nakshatra_telugu: str
    
    # Month
    masa_telugu: str
    
    # Yoga & Karana
    yoga: str
    karana: str
    
    # Auspicious times
    sunrise: str
    sunset: str
    rahu_kalam: str
    
    # Graha Sthiti (major planetary positions)
    graha_sthiti: str


# Telugu weekday names
VARA_TELUGU = {
    0: "సోమవారం",      # Monday
    1: "మంగళవారం",     # Tuesday
    2: "బుధవారం",      # Wednesday
    3: "గురువారం",     # Thursday
    4: "శుక్రవారం",    # Friday
    5: "శనివారం",      # Saturday
    6: "ఆదివారం",      # Sunday
}

VARA_ENGLISH = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}

# Telugu month names (approximate solar months)
MASA_TELUGU = {
    1: "పుష్యం",
    2: "మాఘం",
    3: "ఫాల్గుణం",
    4: "చైత్రం",
    5: "వైశాఖం",
    6: "జ్యేష్ఠం",
    7: "ఆషాఢం",
    8: "శ్రావణం",
    9: "భాద్రపదం",
    10: "ఆశ్వయుజం",
    11: "కార్తీకం",
    12: "మార్గశిరం",
}

# 27 Nakshatras
NAKSHATRAS_TELUGU = [
    ("Ashwini", "అశ్వని"),
    ("Bharani", "భరణి"),
    ("Krittika", "కృత్తిక"),
    ("Rohini", "రోహిణి"),
    ("Mrigashira", "మృగశిర"),
    ("Ardra", "ఆర్ద్ర"),
    ("Punarvasu", "పునర్వసు"),
    ("Pushya", "పుష్యమి"),
    ("Ashlesha", "ఆశ్లేష"),
    ("Magha", "మఘ"),
    ("Purva Phalguni", "పుబ్బ"),
    ("Uttara Phalguni", "ఉత్తర"),
    ("Hasta", "హస్త"),
    ("Chitra", "చిత్త"),
    ("Swati", "స్వాతి"),
    ("Vishakha", "విశాఖ"),
    ("Anuradha", "అనూరాధ"),
    ("Jyeshtha", "జ్యేష్ఠ"),
    ("Mula", "మూల"),
    ("Purva Ashadha", "పూర్వాషాఢ"),
    ("Uttara Ashadha", "ఉత్తరాషాఢ"),
    ("Shravana", "శ్రవణం"),
    ("Dhanishta", "ధనిష్ఠ"),
    ("Shatabhisha", "శతభిషం"),
    ("Purva Bhadrapada", "పూర్వాభాద్ర"),
    ("Uttara Bhadrapada", "ఉత్తరాభాద్ర"),
    ("Revati", "రేవతి"),
]

# 30 Tithis
TITHIS_TELUGU = [
    ("Pratipada", "పాడ్యమి", 1),
    ("Dwitiya", "విదియ", 2),
    ("Tritiya", "తదియ", 3),
    ("Chaturthi", "చవితి", 4),
    ("Panchami", "పంచమి", 5),
    ("Shashthi", "షష్ఠి", 6),
    ("Saptami", "సప్తమి", 7),
    ("Ashtami", "అష్టమి", 8),
    ("Navami", "నవమి", 9),
    ("Dashami", "దశమి", 10),
    ("Ekadashi", "ఏకాదశి", 11),
    ("Dwadashi", "ద్వాదశి", 12),
    ("Trayodashi", "త్రయోదశి", 13),
    ("Chaturdashi", "చతుర్దశి", 14),
    ("Purnima", "పౌర్ణమి", 15),
    ("Amavasya", "అమావాస్య", 30),
]


class PanchangService:
    """Service for calculating/fetching daily Panchang data."""
    
    def __init__(self):
        pass
    
    async def get_panchang(self, target_date: Optional[date] = None) -> PanchangData:
        """
        Get Panchang data for the given date.
        
        For production, this should integrate with a Panchang API or
        astronomical calculation library. Currently uses approximations.
        """
        if target_date is None:
            target_date = date.today()
        
        # Get weekday (Python: Monday=0, Sunday=6)
        weekday = target_date.weekday()
        vara_english = VARA_ENGLISH[weekday]
        vara_telugu = VARA_TELUGU[weekday]
        
        # Get approximate Telugu month
        masa_telugu = MASA_TELUGU[target_date.month]
        
        # Calculate approximate Tithi (lunar day)
        # This is a simplified calculation - for production use a proper library
        tithi_info = self._calculate_approximate_tithi(target_date)
        
        # Calculate approximate Nakshatra
        nakshatra_info = self._calculate_approximate_nakshatra(target_date)
        
        # Determine Paksha (శుక్ల/కృష్ణ)
        paksha = tithi_info["paksha"]
        
        # Generate planetary position summary
        graha_sthiti = self._get_graha_sthiti(target_date)
        
        return PanchangData(
            date=target_date,
            vara_english=vara_english,
            vara_telugu=vara_telugu,
            tithi_name=tithi_info["english"],
            tithi_telugu=tithi_info["telugu"],
            paksha=paksha,
            nakshatra_name=nakshatra_info["english"],
            nakshatra_telugu=nakshatra_info["telugu"],
            masa_telugu=masa_telugu,
            yoga="శుభ",  # Simplified
            karana="బవ",  # Simplified
            sunrise="06:30",
            sunset="18:15",
            rahu_kalam=self._get_rahu_kalam(weekday),
            graha_sthiti=graha_sthiti,
        )
    
    def _calculate_approximate_tithi(self, target_date: date) -> Dict[str, str]:
        """Calculate approximate Tithi based on lunar cycle."""
        # Simplified calculation using a known new moon date
        # Reference: Jan 29, 2025 was Amavasya (approximate)
        reference_amavasya = date(2025, 1, 29)
        days_since = (target_date - reference_amavasya).days
        
        lunar_cycle = 29.53  # days
        days_in_cycle = days_since % lunar_cycle
        tithi_number = int(days_in_cycle / 2) + 1
        
        if tithi_number <= 15:
            paksha = "శుక్ల పక్షం"
        else:
            paksha = "కృష్ణ పక్షం"
            tithi_number = tithi_number - 15
        
        # Get Tithi name
        if tithi_number > 15:
            tithi_number = 15
        
        tithi_data = TITHIS_TELUGU[min(tithi_number - 1, len(TITHIS_TELUGU) - 1)]
        
        return {
            "english": tithi_data[0],
            "telugu": tithi_data[1],
            "paksha": paksha,
        }
    
    def _calculate_approximate_nakshatra(self, target_date: date) -> Dict[str, str]:
        """Calculate approximate Nakshatra."""
        # Simplified: Nakshatra changes roughly every day
        # Reference: Use day of year to cycle through 27 Nakshatras
        day_of_year = target_date.timetuple().tm_yday
        nakshatra_index = day_of_year % 27
        
        nakshatra = NAKSHATRAS_TELUGU[nakshatra_index]
        return {
            "english": nakshatra[0],
            "telugu": nakshatra[1],
        }
    
    def _get_rahu_kalam(self, weekday: int) -> str:
        """Get Rahu Kalam for the day."""
        # Standard Rahu Kalam times
        rahu_times = {
            0: "07:30 - 09:00",  # Monday
            1: "15:00 - 16:30",  # Tuesday
            2: "12:00 - 13:30",  # Wednesday
            3: "13:30 - 15:00",  # Thursday
            4: "10:30 - 12:00",  # Friday
            5: "09:00 - 10:30",  # Saturday
            6: "16:30 - 18:00",  # Sunday
        }
        return rahu_times.get(weekday, "")
    
    def _get_graha_sthiti(self, target_date: date) -> str:
        """
        Get planetary position summary.
        
        For production, integrate with Vedic astrology API.
        Currently returns a generic meaningful statement.
        """
        weekday = target_date.weekday()
        
        # Day-based planetary influences
        day_influences = {
            0: "చంద్రుడు అనుకూలంగా ఉన్నారు",  # Monday - Moon
            1: "కుజుడు బలంగా ఉన్నారు",         # Tuesday - Mars
            2: "బుధుడు శుభంగా ఉన్నారు",        # Wednesday - Mercury
            3: "గురుడు ఆశీర్వదిస్తున్నారు",    # Thursday - Jupiter
            4: "శుక్రుడు అనుకూలం",             # Friday - Venus
            5: "శని ప్రభావం సాధారణం",          # Saturday - Saturn
            6: "సూర్యుడు తేజస్సు ఇస్తున్నారు", # Sunday - Sun
        }
        
        return day_influences.get(weekday, "గ్రహస్థితి సాధారణం")


# Singleton instance
_panchang_service: Optional[PanchangService] = None


def get_panchang_service() -> PanchangService:
    """Get PanchangService instance."""
    global _panchang_service
    if _panchang_service is None:
        _panchang_service = PanchangService()
    return _panchang_service
