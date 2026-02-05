"""
Test Script: Admin API Operations
Test the admin endpoints for broadcasting and seva management.
"""

import httpx
import json

# Configuration
BASE_URL = "http://localhost:8000"  # Change to your deployed URL
ADMIN_API_KEY = "kSOm6IjkENmMXriBSz1m2pOzV-vKIBZpbHaU690Xjp8"  # From your .env


def get_headers():
    """Get headers with admin API key."""
    return {
        "Content-Type": "application/json",
        "X-Admin-API-Key": ADMIN_API_KEY
    }


def test_health():
    """Test health endpoint."""
    print("\n📍 Testing Health Endpoint...")
    response = httpx.get(f"{BASE_URL}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
    return response.status_code == 200


def trigger_daily_rashiphalalu():
    """Manually trigger daily Rashiphalalu broadcast."""
    print("\n📍 Triggering Daily Rashiphalalu Broadcast...")
    try:
        response = httpx.post(
            f"{BASE_URL}/admin/broadcast/daily-rashiphalalu",
            headers=get_headers(),
            timeout=60.0
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")


def trigger_weekly_sankalp():
    """Manually trigger weekly Sankalp prompts."""
    print("\n📍 Triggering Weekly Sankalp Prompts...")
    try:
        response = httpx.post(
            f"{BASE_URL}/admin/broadcast/weekly-sankalp",
            headers=get_headers(),
            timeout=60.0
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")


def get_pending_seva():
    """Get pending seva amounts for transfer."""
    print("\n📍 Getting Pending Seva Amounts...")
    try:
        response = httpx.get(
            f"{BASE_URL}/admin/seva/pending",
            headers=get_headers(),
            timeout=30.0
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Pending Seva: ${data.get('pending_amount', 0):.2f}")
            print(f"   Entries: {data.get('entry_count', 0)}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")


def get_seva_summary():
    """Get seva ledger summary."""
    print("\n📍 Getting Seva Summary...")
    try:
        response = httpx.get(
            f"{BASE_URL}/admin/seva/summary",
            headers=get_headers(),
            timeout=30.0
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Error: {e}")


if __name__ == "__main__":
    print("="*60)
    print("🙏 SUBHAMASTHU ADMIN API TEST")
    print("="*60)
    
    if not test_health():
        print("\n⚠️  Server is not healthy. Exiting.")
        exit(1)
    
    print("\nChoose operation:")
    print("1. Trigger Daily Rashiphalalu")
    print("2. Trigger Weekly Sankalp")
    print("3. Get Pending Seva")
    print("4. Get Seva Summary")
    print("5. Run All Tests")
    
    choice = input("\nEnter choice (1-5): ").strip()
    
    if choice == "1":
        trigger_daily_rashiphalalu()
    elif choice == "2":
        trigger_weekly_sankalp()
    elif choice == "3":
        get_pending_seva()
    elif choice == "4":
        get_seva_summary()
    elif choice == "5":
        trigger_daily_rashiphalalu()
        trigger_weekly_sankalp()
        get_pending_seva()
        get_seva_summary()
    else:
        print("Invalid choice.")
    
    print("\n" + "="*60)
    print("✅ Test Complete!")
    print("="*60)
