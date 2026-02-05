"""
Test Script: Simulate Onboarding Flow
This script simulates the WhatsApp onboarding conversation by calling the Gupshup webhook directly.
"""

import httpx
import json
import time
import uuid
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"  # Change to your deployed URL
TEST_PHONE = "919876543210"  # Test phone number

def create_gupshup_payload(message_text: str, button_payload: str = None) -> dict:
    """Create a Gupshup webhook payload."""
    base_payload = {
        "app": "SubhamasthuApp",
        "timestamp": int(datetime.now().timestamp() * 1000),
        "version": 2,
        "type": "message",
        "payload": {
            "id": str(uuid.uuid4()),
            "source": TEST_PHONE,
            "type": "text" if not button_payload else "button_reply",
            "payload": {
                "text": message_text
            } if not button_payload else {
                "title": message_text,
                "id": button_payload
            },
            "sender": {
                "phone": TEST_PHONE,
                "name": "Test User",
                "country_code": "91"
            }
        }
    }
    return base_payload


def send_message(message: str, button_payload: str = None, delay: float = 1.0):
    """Send a simulated message to the webhook."""
    payload = create_gupshup_payload(message, button_payload)
    
    print(f"\n{'='*60}")
    print(f"📱 Sending: {message}")
    if button_payload:
        print(f"   Button ID: {button_payload}")
    print(f"{'='*60}")
    
    try:
        response = httpx.post(
            f"{BASE_URL}/webhooks/gupshup",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30.0
        )
        print(f"✅ Response: {response.status_code}")
        if response.text:
            try:
                print(f"   Body: {json.dumps(response.json(), indent=2)}")
            except:
                print(f"   Body: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    time.sleep(delay)


def simulate_onboarding():
    """Simulate the complete onboarding flow."""
    print("\n" + "="*60)
    print("🙏 SUBHAMASTHU ONBOARDING SIMULATION")
    print("="*60)
    
    # Step 1: New user says hi
    print("\n📍 Step 1: User initiates conversation")
    send_message("Hi")
    
    # Step 2: Select Rashi
    print("\n📍 Step 2: Select Rashi (Mesha)")
    send_message("మేషం", "RASHI_MESHA")
    
    # Step 3: Optional - Skip Nakshatra
    print("\n📍 Step 3: Skip Nakshatra (optional)")
    send_message("Skip", "SKIP_NAKSHATRA")
    
    # Step 4: Optional - Skip Birth Time
    print("\n📍 Step 4: Skip Birth Time (optional)")
    send_message("Skip", "SKIP_BIRTH_TIME")
    
    # Step 5: Select Deity
    print("\n📍 Step 5: Select Deity (Shiva)")
    send_message("శివ", "DEITY_SHIVA")
    
    # Step 6: Select Auspicious Day
    print("\n📍 Step 6: Select Auspicious Day (Monday)")
    send_message("సోమవారం", "DAY_MONDAY")
    
    print("\n" + "="*60)
    print("✅ ONBOARDING COMPLETE!")
    print("="*60)


def simulate_onboarding_with_details():
    """Simulate onboarding WITH nakshatra and birth time."""
    print("\n" + "="*60)
    print("🙏 SUBHAMASTHU ONBOARDING (WITH ALL DETAILS)")
    print("="*60)
    
    # Step 1: New user says hi
    print("\n📍 Step 1: User initiates conversation")
    send_message("Namaste")
    
    # Step 2: Select Rashi
    print("\n📍 Step 2: Select Rashi (Vrishabha)")
    send_message("వృషభం", "RASHI_VRISHABHA")
    
    # Step 3: Provide Nakshatra
    print("\n📍 Step 3: Provide Nakshatra (Rohini)")
    send_message("రోహిణి", "NAKSH_ROHINI")
    
    # Step 4: Provide Birth Time
    print("\n📍 Step 4: Provide Birth Time")
    send_message("06:30")
    
    # Step 5: Select Deity
    print("\n📍 Step 5: Select Deity (Vishnu)")
    send_message("విష్ణు", "DEITY_VISHNU")
    
    # Step 6: Select Auspicious Day
    print("\n📍 Step 6: Select Auspicious Day (Thursday)")
    send_message("గురువారం", "DAY_THURSDAY")
    
    print("\n" + "="*60)
    print("✅ ONBOARDING COMPLETE WITH ALL DETAILS!")
    print("="*60)


def check_health():
    """Check if the server is running."""
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        if response.status_code == 200:
            print(f"✅ Server is healthy: {response.json()}")
            return True
        else:
            print(f"❌ Server returned: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    print("🔍 Checking server health...")
    if not check_health():
        print("\n⚠️  Server is not running. Start it with:")
        print("   uvicorn app.main:app --reload")
        sys.exit(1)
    
    print("\nChoose simulation:")
    print("1. Quick onboarding (skip optional fields)")
    print("2. Full onboarding (with nakshatra & birth time)")
    print("3. Health check only")
    
    choice = input("\nEnter choice (1/2/3): ").strip()
    
    if choice == "1":
        simulate_onboarding()
    elif choice == "2":
        simulate_onboarding_with_details()
    elif choice == "3":
        print("✅ Health check passed!")
    else:
        print("Invalid choice. Running quick onboarding...")
        simulate_onboarding()
