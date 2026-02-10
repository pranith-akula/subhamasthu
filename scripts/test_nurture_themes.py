
import asyncio
import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.append(os.getcwd())

from app.services.nurture_service import NurtureService
from app.config import settings

async def test_themes():
    # Mock DB session (not needed for _get_content if we don't call it from process_nurture)
    service = NurtureService(None)
    
    test_cases = [
        {"day": 1, "cycle": 1, "track": "DEVOTION", "desc": "Cycle 1 Week 1: Tirumala"},
        {"day": 11, "cycle": 2, "track": "SECURITY", "desc": "Cycle 2 Week 2: Gajendra Moksham"},
        {"day": 20, "cycle": 3, "track": "GROWTH", "desc": "Cycle 3 Week 3: Tyagaraja"},
        {"day": 27, "cycle": 4, "track": "DEVOTION", "desc": "Cycle 4 Week 4: Dharma"},
        {"day": 7, "cycle": 1, "track": "SECURITY", "desc": "Sankalp Invite Day"},
    ]
    
    print("\n--- Testing Nurture Theme Generation ---\n")
    
    for tc in test_cases:
        print(f"Testing: {tc['desc']} (Day {tc['day']}, Cycle {tc['cycle']})")
        content = await service._get_content(day=tc['day'], track=tc['track'], cycle=tc['cycle'], user_name="ప్రసాద్")
        
        if content:
            print(f"Type: {content.get('type')}")
            print(f"Body: {content.get('body')}")
            if content.get('buttons'):
                print(f"Buttons: {content.get('buttons')}")
        else:
            print("FAILED: No content generated.")
        print("-" * 30)

if __name__ == "__main__":
    if not settings.openai_api_key:
        print("ERROR: OPENAI_API_KEY not set.")
    else:
        asyncio.run(test_themes())
