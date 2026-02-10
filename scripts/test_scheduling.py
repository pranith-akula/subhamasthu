
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import logging

# Mock objects/classes
class User:
    def __init__(self):
        self.phone = "1234567890"
        self.tz = "America/Chicago"
        self.next_rashi_at = None
        self.next_nurture_at = None
        self.nurture_day = 0
        self.onboarded_at = None

class TestSchedulingLogic(unittest.TestCase):
    def test_finish_onboarding_logic(self):
        user = User()
        
        # Simulated logic from FSMMachine._finish_onboarding_flow
        user.onboarded_at = datetime.now(timezone.utc)
        
        try:
            tz = ZoneInfo(user.tz or "America/Chicago")
        except Exception:
            tz = ZoneInfo("America/Chicago")
            
        now_local = datetime.now(tz)
        
        # Next Rashi: First 7 AM in the future
        next_rashi = now_local.replace(hour=7, minute=0, second=0, microsecond=0)
        if next_rashi <= now_local:
            next_rashi += timedelta(days=1)
        user.next_rashi_at = next_rashi.astimezone(timezone.utc)
        
        # Next Nurture: First 9 PM in the future
        next_nurture = now_local.replace(hour=21, minute=0, second=0, microsecond=0)
        if next_nurture <= now_local:
            next_nurture += timedelta(days=1)
        user.next_nurture_at = next_nurture.astimezone(timezone.utc)
        
        if not user.nurture_day or user.nurture_day == 0:
            user.nurture_day = 1

        # Assertions
        print(f"User Local Time: {now_local}")
        print(f"Next Rashi (UTC): {user.next_rashi_at}")
        print(f"Next Nurture (UTC): {user.next_nurture_at}")
        
        self.assertIsNotNone(user.next_rashi_at)
        self.assertIsNotNone(user.next_nurture_at)
        self.assertEqual(user.nurture_day, 1)
        self.assertTrue(user.next_rashi_at > datetime.now(timezone.utc))
        self.assertTrue(user.next_nurture_at > datetime.now(timezone.utc))
        
        # Check hour (in local time)
        self.assertEqual(user.next_rashi_at.astimezone(tz).hour, 7)
        self.assertEqual(user.next_nurture_at.astimezone(tz).hour, 21)

    def test_timezone_switching(self):
        # Test with IST
        user = User()
        user.tz = "Asia/Kolkata"
        
        tz = ZoneInfo(user.tz)
        now_local = datetime.now(tz)
        
        # Next Rashi: First 7 AM in the future
        next_rashi = now_local.replace(hour=7, minute=0, second=0, microsecond=0)
        if next_rashi <= now_local:
            next_rashi += timedelta(days=1)
        user.next_rashi_at = next_rashi.astimezone(timezone.utc)
        
        self.assertEqual(user.next_rashi_at.astimezone(tz).hour, 7)
        print(f"IST Next Rashi (UTC): {user.next_rashi_at}")

if __name__ == "__main__":
    unittest.main()
