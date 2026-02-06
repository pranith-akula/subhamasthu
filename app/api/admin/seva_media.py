"""
Admin API for Seva Media management.
Upload footage and manage the proof pool.
"""

import logging
from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.seva_proof_service import SevaProofService
from app.models.seva_media import MediaType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/seva-media", tags=["Admin - Seva Media"])


@router.post("/add")
async def add_seva_media(
    cloudinary_url: str = Form(..., description="Cloudinary URL of uploaded media"),
    media_type: str = Form("image", description="'image' or 'video'"),
    temple_name: Optional[str] = Form(None, description="Temple name (optional)"),
    location: Optional[str] = Form(None, description="Location (optional)"),
    seva_date: Optional[str] = Form(None, description="Seva date YYYY-MM-DD (optional)"),
    families_fed: Optional[int] = Form(None, description="Number of families fed (optional)"),
    caption: Optional[str] = Form(None, description="Custom caption (optional)"),
    cloudinary_public_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Add media to the seva proof pool.
    
    You upload to Cloudinary first, then provide the URL here.
    Metadata is optional - system uses Hyderabad temple fallbacks.
    """
    service = SevaProofService(db)
    
    # Parse media type
    mt = MediaType.VIDEO if media_type.lower() == "video" else MediaType.IMAGE
    
    # Parse seva date if provided
    sd = None
    if seva_date:
        try:
            sd = date.fromisoformat(seva_date)
        except ValueError:
            pass
    
    media = await service.add_media(
        cloudinary_url=cloudinary_url,
        media_type=mt,
        temple_name=temple_name,
        location=location,
        seva_date=sd,
        families_fed=families_fed,
        caption=caption,
        cloudinary_public_id=cloudinary_public_id,
    )
    
    return {
        "status": "success",
        "media_id": str(media.id),
        "message": "Media added to pool",
    }


@router.get("/pool-stats")
async def get_pool_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get statistics about the seva media pool."""
    service = SevaProofService(db)
    stats = await service.get_pool_stats()
    
    return {
        "status": "success",
        "pool": stats,
    }


@router.get("/list")
async def list_seva_media(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List media items for the admin gallery."""
    from sqlalchemy import select, desc
    from app.models.seva_media import SevaMedia
    
    query = select(SevaMedia).order_by(desc(SevaMedia.created_at)).limit(limit).offset(offset)
    result = await db.execute(query)
    media_list = result.scalars().all()
    
    return {
        "status": "success",
        "items": [
            {
                "id": str(m.id),
                "url": m.cloudinary_url,
                "type": m.media_type,
                "date": m.created_at.isoformat() if m.created_at else None,
                "used": m.used_count,
                "caption": m.caption
            } for m in media_list
        ]
    }


@router.post("/send-test")
async def send_test_proof(
    phone: str = Form(..., description="Phone number to send test to"),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a test seva proof to a phone number.
    Useful for testing the feature.
    """
    from app.models.user import User
    from app.models.sankalp import Sankalp
    from sqlalchemy import select
    
    # Get user by phone
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get latest sankalp for user
    result = await db.execute(
        select(Sankalp)
        .where(Sankalp.user_id == user.id)
        .order_by(Sankalp.created_at.desc())
        .limit(1)
    )
    sankalp = result.scalar_one_or_none()
    
    if not sankalp:
        raise HTTPException(status_code=404, detail="No sankalp found for user")
    
    service = SevaProofService(db)
    success = await service.send_proof_to_donor(user, sankalp)
    
    if success:
        return {"status": "success", "message": "Test proof sent"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send proof")


@router.post("/trigger-daily-job")
async def trigger_daily_job(
    db: AsyncSession = Depends(get_db),
):
    """
    Manually trigger the daily seva proof job.
    Normally runs at 11am automatically.
    """
    service = SevaProofService(db)
    sent = await service.send_proof_to_yesterday_donors()
    
    return {
        "status": "success",
        "donors_notified": sent,
    }
