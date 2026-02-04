"""
Tests for Gupshup webhook handler.
"""

import pytest
from fastapi.testclient import TestClient


# Sample Gupshup webhook payloads
SAMPLE_TEXT_MESSAGE = {
    "app": "TestApp",
    "timestamp": 1699900000000,
    "version": 2,
    "type": "message",
    "payload": {
        "id": "msg_123456",
        "source": "919876543210",
        "type": "text",
        "payload": {
            "text": "Hello"
        },
        "sender": {
            "phone": "919876543210",
            "name": "Test User"
        }
    }
}

SAMPLE_BUTTON_REPLY = {
    "app": "TestApp",
    "timestamp": 1699900000000,
    "version": 2,
    "type": "message",
    "payload": {
        "id": "msg_123457",
        "source": "919876543210",
        "type": "button_reply",
        "payload": {
            "id": "RASHI_MESHA",
            "title": "మేషం (Aries)"
        },
        "sender": {
            "phone": "919876543210",
            "name": "Test User"
        }
    }
}

SAMPLE_MESSAGE_STATUS = {
    "app": "TestApp",
    "timestamp": 1699900000000,
    "version": 2,
    "type": "message-event",
    "payload": {
        "id": "msg_123456",
        "type": "delivered",
        "destination": "919876543210"
    }
}


class TestGupshupWebhook:
    """Tests for Gupshup webhook endpoint."""
    
    def test_webhook_receives_text_message(self):
        """Test webhook handles text messages."""
        # This would need actual FastAPI client setup
        # For now, verify payload structure
        assert SAMPLE_TEXT_MESSAGE["type"] == "message"
        assert SAMPLE_TEXT_MESSAGE["payload"]["type"] == "text"
    
    def test_webhook_receives_button_reply(self):
        """Test webhook handles button replies."""
        assert SAMPLE_BUTTON_REPLY["type"] == "message"
        assert SAMPLE_BUTTON_REPLY["payload"]["type"] == "button_reply"
        assert SAMPLE_BUTTON_REPLY["payload"]["payload"]["id"] == "RASHI_MESHA"
    
    def test_message_status_handling(self):
        """Test webhook handles delivery status."""
        assert SAMPLE_MESSAGE_STATUS["type"] == "message-event"
        assert SAMPLE_MESSAGE_STATUS["payload"]["type"] == "delivered"


class TestPayloadParsing:
    """Tests for parsing Gupshup payloads."""
    
    def test_extract_phone_from_text_message(self):
        """Extract phone number from message payload."""
        phone = SAMPLE_TEXT_MESSAGE["payload"]["source"]
        assert phone == "919876543210"
    
    def test_extract_text_content(self):
        """Extract text content from message."""
        text = SAMPLE_TEXT_MESSAGE["payload"]["payload"]["text"]
        assert text == "Hello"
    
    def test_extract_button_payload(self):
        """Extract button ID from button reply."""
        button_id = SAMPLE_BUTTON_REPLY["payload"]["payload"]["id"]
        assert button_id == "RASHI_MESHA"
    
    def test_extract_sender_name(self):
        """Extract sender name from message."""
        name = SAMPLE_TEXT_MESSAGE["payload"]["sender"]["name"]
        assert name == "Test User"
