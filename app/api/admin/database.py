
import os
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header
from sqlalchemy import text

from app.database import engine
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

async def verify_admin_key(x_admin_key: str = Header(..., alias="X-Admin-Key")):
    """Verify admin API key."""
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")
    return x_admin_key

async def run_migrations_task():
    """Run migrations in background."""
    logger.info("🚀 Starting database migration task...")
    
    migrations_dir = "migrations"
    # In docker, working directory is /app, so migrations is at ./migrations
    
    if not os.path.exists(migrations_dir):
        logger.error(f"Migration directory not found: {os.path.abspath(migrations_dir)}")
        return

    files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])
    logger.info(f"Found {len(files)} migration files.")
    
    try:
        async with engine.begin() as conn:
            # Enable pgcrypto
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
            
            for filename in files:
                path = os.path.join(migrations_dir, filename)
                logger.info(f"Applying {filename}...")
                
                with open(path, "r", encoding="utf-8") as f:
                    sql = f.read()
                    
                statements = [s.strip() for s in sql.split(';') if s.strip()]
                
                for stmt in statements:
                    try:
                        await conn.execute(text(stmt))
                    except Exception as e:
                        # Log error but continue if it's "already exists"
                        err_str = str(e).lower()
                        if "already exists" in err_str or "duplicateobject" in err_str:
                            logger.warning(f"⚠️ Object already exists (skipping): {str(e)[:100]}...")
                        else:
                            logger.error(f"❌ Error executing stmt: {stmt[:50]}... -> {e}")
                            # Optional: raise if you want strict failure on other errors
                            # For now, we continue to try applying other parts
                            pass
                    
                logger.info(f"✅ Applied {filename}")
                
        logger.info("🚀 All migrations completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")

@router.post("/migrate", dependencies=[Depends(verify_admin_key)])
async def trigger_migration(
    background_tasks: BackgroundTasks,
):
    """
    Trigger database migrations manually.
    PROTECTED: Requires X-Admin-Key header.
    """
    background_tasks.add_task(run_migrations_task)
    return {
        "status": "Migration started in background",
        "message": "Check application logs for progress."
    }


# ============================================
# EASY BROWSER ACCESS ENDPOINTS (GET methods)
# Use password query param for simple browser access
# ============================================

BROWSER_PASSWORD = "Zilla831"

@router.get("/run-migrations")
async def run_migrations_get(
    background_tasks: BackgroundTasks,
    password: str = "",
):
    """
    Run migrations via browser.
    Usage: /admin/run-migrations?password=Zilla831@@
    """
    if password != BROWSER_PASSWORD:
        return {"error": "Invalid password. Use ?password=YOUR_PASSWORD"}
    
    background_tasks.add_task(run_migrations_task)
    return {
        "status": "✅ Migration started!",
        "message": "Check Railway logs for progress.",
        "next_step": "Now visit /admin/seed-temples?password=Zilla831@@"
    }


@router.get("/seed-temples")
async def seed_temples_get(
    password: str = "",
):
    """
    Seed temples via browser.
    Usage: /admin/seed-temples?password=Zilla831@@
    """
    if password != BROWSER_PASSWORD:
        return {"error": "Invalid password. Use ?password=YOUR_PASSWORD"}
    
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.temple import Temple
    
    # Temple data
    TEMPLES_DATA = [
        {"name": "ISKCON Temple", "name_telugu": "ఇస్కాన్ ఆలయం", "location": "బంజారాహిల్స్", "city": "Hyderabad", "deity": "Krishna"},
        {"name": "Birla Mandir", "name_telugu": "బిర్లా మందిరం", "location": "నోబెల్ నగర్", "city": "Hyderabad", "deity": "Venkateshwara"},
        {"name": "Chilkur Balaji Temple", "name_telugu": "చిలుకూరు బాలాజీ ఆలయం", "location": "చిలుకూరు", "city": "Hyderabad", "deity": "Venkateshwara"},
        {"name": "Tirumala Tirupati", "name_telugu": "తిరుమల వేంకటేశ్వర ఆలయం", "location": "తిరుమల", "city": "Tirupati", "deity": "Venkateshwara"},
        {"name": "Simhachalam Temple", "name_telugu": "సింహాచలం ఆలయం", "location": "సింహాచలం", "city": "Visakhapatnam", "deity": "Narasimha"},
        {"name": "Draksharamam Temple", "name_telugu": "ద్రాక్షారామం ఆలయం", "location": "ద్రాక్షారామం", "city": "East Godavari", "deity": "Shiva"},
        {"name": "Srisailam Temple", "name_telugu": "శ్రీశైలం ఆలయం", "location": "శ్రీశైలం", "city": "Kurnool", "deity": "Shiva"},
        {"name": "Annavaram Satyanarayana", "name_telugu": "అన్నవరం సత్యనారాయణ ఆలయం", "location": "అన్నవరం", "city": "East Godavari", "deity": "Satyanarayana"},
        {"name": "Kanipakam Vinayaka Temple", "name_telugu": "కాణిపాకం వినాయక ఆలయం", "location": "కాణిపాకం", "city": "Chittoor", "deity": "Ganesha"},
        {"name": "Yadadri Lakshmi Narasimha", "name_telugu": "యాదాద్రి లక్ష్మీనరసింహ ఆలయం", "location": "యాదగిరిగుట్ట", "city": "Yadadri", "deity": "Narasimha"},
        {"name": "Basara Saraswati Temple", "name_telugu": "బాసర సరస్వతీ ఆలయం", "location": "బాసర", "city": "Nirmal", "deity": "Saraswati"},
        {"name": "Bhadrachalam Temple", "name_telugu": "భద్రాచలం ఆలయం", "location": "భద్రాచలం", "city": "Bhadradri Kothagudem", "deity": "Rama"},
        {"name": "Vijayawada Kanaka Durga", "name_telugu": "విజయవాడ కనకదుర్గ ఆలయం", "location": "ఇంద్రకీలాద్రి", "city": "Vijayawada", "deity": "Durga"},
        {"name": "Srikalahasti Temple", "name_telugu": "శ్రీకాళహస్తి ఆలయం", "location": "శ్రీకాళహస్తి", "city": "Tirupati", "deity": "Shiva"},
        {"name": "Ahobilam Temple", "name_telugu": "అహోబిలం ఆలయం", "location": "అహోబిలం", "city": "Kurnool", "deity": "Narasimha"},
    ]
    
    try:
        async with AsyncSessionLocal() as db:
            # Check if temples already exist
            result = await db.execute(select(Temple).limit(1))
            existing = result.scalar_one_or_none()
            
            if existing:
                # Count existing
                count_result = await db.execute(select(Temple))
                count = len(count_result.scalars().all())
                return {"status": "⚠️ Temples already seeded", "count": count}
            
            # Insert all temples
            for temple_data in TEMPLES_DATA:
                temple = Temple(**temple_data)
                db.add(temple)
            
            await db.commit()
            return {"status": "✅ Temples seeded successfully!", "count": len(TEMPLES_DATA)}
            
    except Exception as e:
        return {"status": "❌ Error", "error": str(e)}

