"""
Automatic Seva Footage Watcher
------------------------------
Monitors the 'seva_videos' folder.
When a video is dropped, it automatically:
1. Uploads to Cloudinary
2. Adds to DB pool
3. Moves to 'uploaded' folder

Usage:
    python scripts/watch_footage.py
"""

import sys
import os
import time
import shutil
import asyncio
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cloudinary
import cloudinary.uploader
from app.config import settings
from app.database import get_db_context as get_db_session
from app.services.seva_proof_service import SevaProofService
from app.models.seva_media import MediaType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler("watcher.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure Cloudinary
if not settings.cloudinary_cloud_name:
    logger.error("❌ Cloudinary settings missing in .env")
    sys.exit(1)

cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
    secure=True
)

ALLOWED_EXTENSIONS = {
    'image': ['.jpg', '.jpeg', '.png', '.webp'],
    'video': ['.mp4', '.mov', '.avi', '.webm']
}

WATCH_DIR = Path("seva_videos")
UPLOADED_DIR = WATCH_DIR / "uploaded"

async def process_file(file_path: Path):
    """Upload and record file."""
    filename = file_path.name
    ext = file_path.suffix.lower()
    
    # Determine type
    media_type = None
    if ext in ALLOWED_EXTENSIONS['image']:
        media_type = MediaType.IMAGE
    elif ext in ALLOWED_EXTENSIONS['video']:
        media_type = MediaType.VIDEO
    else:
        return None
    
    logger.info(f"Detected new file: {filename}")
    
    # Wait for file copy to complete (simple stability check)
    size = -1
    retries = 0
    while retries < 10:
        try:
            current_size = file_path.stat().st_size
            if current_size == size:
                break
            size = current_size
            time.sleep(0.5)
            retries += 1
        except Exception:
            time.sleep(0.5)
            pass
            
    logger.info(f"Uploading {filename} to Cloudinary...")
    
    try:
        # Upload
        resource_type = "video" if media_type == MediaType.VIDEO else "image"
        
        # Run synchronous upload in thread pool
        response = await asyncio.to_thread(
            cloudinary.uploader.upload,
            str(file_path),
            resource_type=resource_type,
            folder="subhamasthu/seva_proofs"
        )
        
        url = response.get("secure_url")
        public_id = response.get("public_id")
        
        if not url:
            logger.error(f"Upload failed for {filename}")
            return False

        # Add to DB
        async with get_db_session() as db:
            service = SevaProofService(db)
            await service.add_media(
                cloudinary_url=url,
                media_type=media_type,
                cloudinary_public_id=public_id,
                caption=f"Auto-uploaded: {filename}"
            )
            
        logger.info(f"Added to DB: {filename}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing {filename}: {e}")
        return False
        
    # ... inside Handler ...
        
        if success:
            # Move to uploaded folder
            try:
                dest = UPLOADED_DIR / file_path.name
                shutil.move(str(file_path), str(dest))
                logger.info(f"Moved to uploaded: {dest}")
            except Exception as e:
                logger.error(f"Failed to move file: {e}") 

# ... inside main ...
    
    logging.info(f"Watching directory: {WATCH_DIR.absolute()}")
    logging.info("Drop video files here to auto-upload.")


class FootageHandler(FileSystemEventHandler):
    """Watchdog handler for new files."""
    
    def on_created(self, event):
        if event.is_directory:
            return
            
        src_path = Path(event.src_path)
        
        # Ignore if in uploaded dir
        if "uploaded" in str(src_path):
            return
            
        # Ignore hidden files
        if src_path.name.startswith("."):
            return

        # Run async process
        asyncio.run(self._handle_file(src_path))
        
    async def _handle_file(self, file_path: Path):
        success = await process_file(file_path)
        
        if success:
            # Move to uploaded folder
            try:
                dest = UPLOADED_DIR / file_path.name
                shutil.move(str(file_path), str(dest))
                logger.info(f"📁 Moved to uploaded: {dest}")
            except Exception as e:
                logger.error(f"⚠️ Failed to move file: {e}")


def main():
    # Ensure dirs exist
    WATCH_DIR.mkdir(exist_ok=True)
    UPLOADED_DIR.mkdir(exist_ok=True)
    
    logging.info(f"Watching directory: {WATCH_DIR.absolute()}")
    logging.info("Drop video files here to auto-upload.")
    
    event_handler = FootageHandler()
    observer = Observer()
    observer.schedule(event_handler, str(WATCH_DIR), recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()


if __name__ == "__main__":
    main()
