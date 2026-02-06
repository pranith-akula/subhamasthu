"""
Bulk Upload Script for Seva Footage
-----------------------------------
Scans a directory for images/videos, uploads to Cloudinary,
and adds them to the Seva Proof pool (seva_medias table).

Usage:
    python scripts/upload_seva_footage.py --dir "C:/path/to/footage"

Requirements:
    pip install cloudinary
"""

import asyncio
import os
import argparse
import sys
import mimetypes
from pathlib import Path

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cloudinary
import cloudinary.uploader

from app.config import settings
from app.database import get_db_context as get_db_session
from app.services.seva_proof_service import SevaProofService
from app.models.seva_media import MediaType

# Configure Cloudinary
if not settings.cloudinary_cloud_name:
    print("❌ Cloudinary settings missing in .env")
    print("Please set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET")
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

async def process_file(file_path: Path, service: SevaProofService):
    """Upload a single file and add to DB."""
    filename = file_path.name
    ext = file_path.suffix.lower()
    
    # Determine type
    media_type = None
    if ext in ALLOWED_EXTENSIONS['image']:
        media_type = MediaType.IMAGE
    elif ext in ALLOWED_EXTENSIONS['video']:
        media_type = MediaType.VIDEO
    else:
        return  # Skip unknown
        
    print(f"Uploading {filename} ({media_type.value})...", end="", flush=True)
    
    try:
        # Upload to Cloudinary
        resource_type = "video" if media_type == MediaType.VIDEO else "image"
        response = cloudinary.uploader.upload(
            str(file_path),
            resource_type=resource_type,
            folder="subhamasthu/seva_proofs"
        )
        
        url = response.get("secure_url")
        public_id = response.get("public_id")
        
        if not url:
            print(" ❌ Cloudinary upload failed")
            return

        # Add to DB
        await service.add_media(
            cloudinary_url=url,
            media_type=media_type,
            cloudinary_public_id=public_id,
            caption=f"Seva footage from {filename}"
        )
        print(" ✅ Done")
        
    except Exception as e:
        print(f" ❌ Error: {e}")

async def main():
    parser = argparse.ArgumentParser(description="Bulk upload seva footage")
    parser.add_argument("--dir", required=True, help="Directory containing photos/videos")
    parser.add_argument("--temple", help="Default temple name")
    parser.add_argument("--location", help="Default location")
    args = parser.parse_args()
    
    directory = Path(args.dir)
    if not directory.exists():
        print(f"Directory not found: {directory}")
        return

    print(f"📂 Scanning {directory}...")
    
    files = [f for f in directory.iterdir() if f.is_file()]
    print(f"Found {len(files)} files.")
    
    async with get_db_session() as db:
        service = SevaProofService(db)
        for f in files:
            await process_file(f, service)
            
    print("\n✨ All done! Footage added to pool.")

if __name__ == "__main__":
    asyncio.run(main())
