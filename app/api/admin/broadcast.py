"""
Admin Broadcast Endpoints.
Manual triggers for daily Rashiphalalu and other broadcasts.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.rashiphalalu_service import RashiphalaluService

router = APIRouter()
logger = logging.getLogger(__name__)


async def verify_admin_key(x_admin_key: Optional[str] = Header(None)) -> None:
    """Verify admin API key from header."""
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


@router.post("/broadcast/rashiphalalu")
async def trigger_rashiphalalu_broadcast(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """
    Manually trigger daily Rashiphalalu broadcast.
    
    This generates messages for all 12 rashis and broadcasts
    to all active users based on their rashi preference.
    """
    try:
        service = RashiphalaluService(db)
        
        # Generate today's messages
        generated_count = await service.generate_daily_messages()
        
        # Broadcast to users
        sent_count = await service.broadcast_to_users()
        
        logger.info(f"Rashiphalalu broadcast complete: {generated_count} generated, {sent_count} sent")
        
        return {
            "status": "success",
            "generated": generated_count,
            "sent": sent_count,
        }
        
    except Exception as e:
        logger.error(f"Rashiphalalu broadcast failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/broadcast/weekly-sankalp")
async def trigger_weekly_sankalp(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """
    Manually trigger weekly sankalp prompts.
    
    Sends reflection prompts to users whose auspicious_day is today
    and who are not in cooldown.
    """
    try:
        from app.services.sankalp_service import SankalpService
        
        service = SankalpService(db)
        sent_count = await service.send_weekly_prompts()
        
        logger.info(f"Weekly sankalp prompts sent: {sent_count}")
        
        return {
            "status": "success",
            "sent": sent_count,
        }
        
    except Exception as e:
        logger.error(f"Weekly sankalp trigger failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
