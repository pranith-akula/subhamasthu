"""
Simple Standalone Watcher for Seva Footage
------------------------------------------
Decoupled from main application to avoid conflicts.
Reads .env directly and inserts via raw SQL.
"""

import sys
import os
import time
import shutil
import logging
import asyncio
from pathlib import Path
from datetime import datetime

# Third-party (must be pip installed)
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import cloudinary
import cloudinary.uploader
import asyncpg

# Configure Logging
log_file = "watcher.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("SevaWatcher")

# Load environment
load_dotenv()

# Cloudinary Config
CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
API_KEY = os.getenv("CLOUDINARY_API_KEY")
API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL")

if not all([CLOUD_NAME, API_KEY, API_SECRET, DATABASE_URL]):
    logger.error("Missing config in .env! Check Cloudinary/DB keys.")
    sys.exit(1)

cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=API_KEY,
    api_secret=API_SECRET,
    secure=True
)

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.mp4', '.mov', '.avi', '.webm'}
WATCH_DIR = Path("seva_videos")
UPLOADED_DIR = WATCH_DIR / "uploaded"

async def insert_into_db(url, public_id, media_type, filename):
    """Insert directly into DB using raw SQL."""
    try:
        # Convert DATABASE_URL from generic postgresql:// to asyncpg friendly if needed
        # But asyncpg usually handles it.
        # If it's `postgresql+asyncpg://`, strip the `+asyncpg`
        dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        
        conn = await asyncpg.connect(dsn)
        try:
            # Check if seva_medias table exists
            # We assume it does (migration fix was applied)
            
            query = """
                INSERT INTO seva_medias (
                    media_type, 
                    cloudinary_url, 
                    cloudinary_public_id, 
                    caption,
                    created_at,
                    used_count
                ) VALUES ($1, $2, $3, $4, NOW(), 0)
            """
            
            # Map media type to simple string (DB column is VARCHAR now)
            m_type = "video" if media_type == "video" else "image"
            
            await conn.execute(
                query, 
                m_type, 
                url, 
                public_id, 
                f"Auto-uploaded: {filename}"
            )
            return True
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"DB Error: {e}")
        return False

async def process_file(file_path: Path):
    filename = file_path.name
    ext = file_path.suffix.lower()
    
    if ext not in ALLOWED_EXTENSIONS:
        return False
        
    logger.info(f"Detected: {filename}")
    
    # Simple stability check (wait for copy)
    size = -1
    for _ in range(10):
        try:
            current = file_path.stat().st_size
            if current == size: break
            size = current
            await asyncio.sleep(0.5)
        except:
            pass
            
    logger.info(f"Uploading {filename}...")
    
    try:
        # Determine resource type
        r_type = "video" if ext in {'.mp4', '.mov', '.avi', '.webm'} else "image"
        
        # Upload
        resp = await asyncio.to_thread(
            cloudinary.uploader.upload,
            str(file_path),
            resource_type=r_type,
            folder="subhamasthu/seva_proofs"
        )
        
        url = resp.get("secure_url")
        pid = resp.get("public_id")
        
        if not url:
            logger.error(f"Upload failed: {filename}")
            return False
            
        # DB Insert
        if await insert_into_db(url, pid, r_type, filename):
            logger.info(f"Success! Added to DB: {filename}")
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return False

class Handler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory: return
        path = Path(event.src_path)
        if "uploaded" in str(path) or path.name.startswith("."): return
        
        asyncio.run(self._handle(path))
        
    async def _handle(self, path):
        if await process_file(path):
            try:
                dest = UPLOADED_DIR / path.name
                shutil.move(str(path), str(dest))
                logger.info(f"Moved to uploaded: {dest.name}")
            except Exception as e:
                logger.error(f"Move failed: {e}")

def main():
    WATCH_DIR.mkdir(exist_ok=True)
    UPLOADED_DIR.mkdir(exist_ok=True)
    
    logger.info(f"Watching: {WATCH_DIR.absolute()}")
    logger.info("Ready for files...")
    
    obs = Observer()
    obs.schedule(Handler(), str(WATCH_DIR), recursive=False)
    obs.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()

if __name__ == "__main__":
    main()
