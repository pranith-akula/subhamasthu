
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
                    await conn.execute(text(stmt))
                    
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
