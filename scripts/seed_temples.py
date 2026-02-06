"""
Seed script to populate temples table with Telugu temple data.
Run: python scripts/seed_temples.py
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.database import engine, AsyncSessionLocal
from app.models.temple import Temple


# 15+ Telugu temples with metadata
TEMPLES_DATA = [
    {
        "name": "ISKCON Temple",
        "name_telugu": "ఇస్కాన్ ఆలయం",
        "location": "బంజారాహిల్స్",
        "city": "Hyderabad",
        "deity": "Krishna",
    },
    {
        "name": "Birla Mandir",
        "name_telugu": "బిర్లా మందిరం",
        "location": "నోబెల్ నగర్",
        "city": "Hyderabad",
        "deity": "Venkateshwara",
    },
    {
        "name": "Chilkur Balaji Temple",
        "name_telugu": "చిలుకూరు బాలాజీ ఆలయం",
        "location": "చిలుకూరు",
        "city": "Hyderabad",
        "deity": "Venkateshwara",
    },
    {
        "name": "Tirumala Tirupati",
        "name_telugu": "తిరుమల వేంకటేశ్వర ఆలయం",
        "location": "తిరుమల",
        "city": "Tirupati",
        "deity": "Venkateshwara",
    },
    {
        "name": "Simhachalam Temple",
        "name_telugu": "సింహాచలం ఆలయం",
        "location": "సింహాచలం",
        "city": "Visakhapatnam",
        "deity": "Narasimha",
    },
    {
        "name": "Draksharamam Temple",
        "name_telugu": "ద్రాక్షారామం ఆలయం",
        "location": "ద్రాక్షారామం",
        "city": "East Godavari",
        "deity": "Shiva",
    },
    {
        "name": "Srisailam Temple",
        "name_telugu": "శ్రీశైలం ఆలయం",
        "location": "శ్రీశైలం",
        "city": "Kurnool",
        "deity": "Shiva",
    },
    {
        "name": "Annavaram Satyanarayana",
        "name_telugu": "అన్నవరం సత్యనారాయణ ఆలయం",
        "location": "అన్నవరం",
        "city": "East Godavari",
        "deity": "Satyanarayana",
    },
    {
        "name": "Kanipakam Vinayaka Temple",
        "name_telugu": "కాణిపాకం వినాయక ఆలయం",
        "location": "కాణిపాకం",
        "city": "Chittoor",
        "deity": "Ganesha",
    },
    {
        "name": "Yadadri Lakshmi Narasimha",
        "name_telugu": "యాదాద్రి లక్ష్మీనరసింహ ఆలయం",
        "location": "యాదగిరిగుట్ట",
        "city": "Yadadri",
        "deity": "Narasimha",
    },
    {
        "name": "Basara Saraswati Temple",
        "name_telugu": "బాసర సరస్వతీ ఆలయం",
        "location": "బాసర",
        "city": "Nirmal",
        "deity": "Saraswati",
    },
    {
        "name": "Bhadrachalam Temple",
        "name_telugu": "భద్రాచలం ఆలయం",
        "location": "భద్రాచలం",
        "city": "Bhadradri Kothagudem",
        "deity": "Rama",
    },
    {
        "name": "Vijayawada Kanaka Durga",
        "name_telugu": "విజయవాడ కనకదుర్గ ఆలయం",
        "location": "ఇంద్రకీలాద్రి",
        "city": "Vijayawada",
        "deity": "Durga",
    },
    {
        "name": "Srikalahasti Temple",
        "name_telugu": "శ్రీకాళహస్తి ఆలయం",
        "location": "శ్రీకాళహస్తి",
        "city": "Tirupati",
        "deity": "Shiva",
    },
    {
        "name": "Ahobilam Temple",
        "name_telugu": "అహోబిలం ఆలయం",
        "location": "అహోబిలం",
        "city": "Kurnool",
        "deity": "Narasimha",
    },
]


async def seed_temples():
    """Seed temples into database."""
    async with AsyncSessionLocal() as db:
        # Check if temples already exist
        result = await db.execute(select(Temple).limit(1))
        existing = result.scalar_one_or_none()
        
        if existing:
            print("⚠️ Temples already seeded. Skipping.")
            return
        
        # Insert all temples
        for temple_data in TEMPLES_DATA:
            temple = Temple(**temple_data)
            db.add(temple)
            print(f"  ✅ Added: {temple_data['name']}")
        
        await db.commit()
        print(f"\n🎉 Successfully seeded {len(TEMPLES_DATA)} temples!")


if __name__ == "__main__":
    print("🛕 Seeding Telugu Temples...\n")
    asyncio.run(seed_temples())
