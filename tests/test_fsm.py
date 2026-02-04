"""
Tests for FSM state machine.
"""

import pytest
from app.fsm.states import (
    ConversationState,
    SankalpCategory,
    SankalpTier,
    SankalpStatus,
    Rashi,
    Deity,
    AuspiciousDay,
)


class TestConversationState:
    """Tests for ConversationState enum."""
    
    def test_all_states_defined(self):
        """Verify all required states are defined."""
        expected_states = [
            "NEW",
            "WAITING_FOR_RASHI",
            "WAITING_FOR_DEITY",
            "WAITING_FOR_AUSPICIOUS_DAY",
            "ONBOARDED",
            "DAILY_PASSIVE",
            "WEEKLY_PROMPT_SENT",
            "WAITING_FOR_CATEGORY",
            "WAITING_FOR_TIER",
            "PAYMENT_LINK_SENT",
            "PAYMENT_CONFIRMED",
            "RECEIPT_SENT",
            "COOLDOWN",
        ]
        
        actual_states = [s.value for s in ConversationState]
        assert set(expected_states) == set(actual_states)
    
    def test_state_string_conversion(self):
        """Test that states convert to strings correctly."""
        assert ConversationState.NEW.value == "NEW"
        assert str(ConversationState.WAITING_FOR_RASHI) == "ConversationState.WAITING_FOR_RASHI"


class TestSankalpCategory:
    """Tests for SankalpCategory enum."""
    
    def test_all_categories_defined(self):
        """Verify all 4 categories are defined."""
        assert len(list(SankalpCategory)) == 4
    
    def test_category_display_names(self):
        """Test Telugu and English display names."""
        assert SankalpCategory.FAMILY.display_name_telugu == "పిల్లలు / పరివారం"
        assert SankalpCategory.FAMILY.display_name_english == "Children / Family"
        
        assert SankalpCategory.HEALTH.display_name_telugu == "ఆరోగ్యం / రక్ష"
        assert SankalpCategory.CAREER.display_name_english == "Career / Financial"
    
    def test_button_payload_format(self):
        """Test that button payloads are in correct format."""
        for cat in SankalpCategory:
            assert cat.value.startswith("CAT_")


class TestSankalpTier:
    """Tests for SankalpTier enum."""
    
    def test_all_tiers_defined(self):
        """Verify all 3 tiers are defined."""
        assert len(list(SankalpTier)) == 3
    
    def test_tier_amounts(self):
        """Test tier amounts are correctly defined in cents."""
        assert SankalpTier.S15.amount_usd == 1500
        assert SankalpTier.S30.amount_usd == 3000
        assert SankalpTier.S50.amount_usd == 5000
    
    def test_tier_display_names(self):
        """Test tier display names."""
        assert "$15" in SankalpTier.S15.display_name
        assert "Samuhik" in SankalpTier.S15.display_name


class TestRashi:
    """Tests for Rashi enum."""
    
    def test_all_12_rashis_defined(self):
        """Verify all 12 rashis are defined."""
        assert len(list(Rashi)) == 12
    
    def test_rashi_telugu_names(self):
        """Test Telugu names are set correctly."""
        assert Rashi.MESHA.telugu_name == "మేషం"
        assert Rashi.VRISHABHA.telugu_name == "వృషభం"
        assert Rashi.MEENA.telugu_name == "మీనం"


class TestDeity:
    """Tests for Deity enum."""
    
    def test_deities_defined(self):
        """Verify deities are defined."""
        assert len(list(Deity)) >= 8
    
    def test_deity_telugu_names(self):
        """Test Telugu names for deities."""
        assert Deity.SHIVA.telugu_name == "శివుడు"
        assert Deity.VISHNU.telugu_name == "విష్ణువు"
        assert Deity.HANUMAN.telugu_name == "హనుమాన్"


class TestAuspiciousDay:
    """Tests for AuspiciousDay enum."""
    
    def test_all_7_days_defined(self):
        """Verify all 7 days are defined."""
        assert len(list(AuspiciousDay)) == 7
    
    def test_day_telugu_names(self):
        """Test Telugu day names."""
        assert AuspiciousDay.MONDAY.telugu_name == "సోమవారం"
        assert AuspiciousDay.FRIDAY.telugu_name == "శుక్రవారం"
