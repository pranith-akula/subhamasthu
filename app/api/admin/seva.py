"""
Admin Seva Endpoints.
Batch creation and transfer management for Annadanam.
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.seva_ledger_service import SevaLedgerService

router = APIRouter()
logger = logging.getLogger(__name__)


async def verify_admin_key(x_admin_key: Optional[str] = Header(None)) -> None:
    """Verify admin API key from header."""
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


class CreateBatchRequest(BaseModel):
    """Request body for creating a seva batch."""
    period_start: date
    period_end: date


class MarkTransferredRequest(BaseModel):
    """Request body for marking batch as transferred."""
    batch_id: str
    transfer_reference: str


@router.post("/seva/batch/create")
async def create_seva_batch(
    request: CreateBatchRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """
    Create a new seva batch for a date range.
    
    Groups all unbatched seva ledger entries from the period.
    """
    try:
        service = SevaLedgerService(db)
        
        batch = await service.create_batch(
            period_start=request.period_start,
            period_end=request.period_end,
        )
        
        logger.info(f"Seva batch created: {batch.batch_id}")
        
        return {
            "status": "success",
            "batch_id": batch.batch_id,
            "total_seva_amount": float(batch.total_seva_amount),
            "period_start": str(batch.period_start),
            "period_end": str(batch.period_end),
        }
        
    except Exception as e:
        logger.error(f"Seva batch creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seva/batch/mark-transferred")
async def mark_batch_transferred(
    request: MarkTransferredRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """
    Mark a seva batch as transferred.
    
    Records the transfer reference (bank/UPI ref).
    """
    try:
        service = SevaLedgerService(db)
        
        batch = await service.mark_transferred(
            batch_id=request.batch_id,
            transfer_reference=request.transfer_reference,
        )
        
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        logger.info(f"Seva batch transferred: {batch.batch_id}")
        
        return {
            "status": "success",
            "batch_id": batch.batch_id,
            "transfer_reference": batch.transfer_reference,
            "transfer_status": batch.transfer_status,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch transfer marking failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/seva/batches")
async def list_batches(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """List all seva batches with their status."""
    try:
        service = SevaLedgerService(db)
        batches = await service.list_batches()
        
        return {
            "status": "success",
            "batches": [
                {
                    "batch_id": b.batch_id,
                    "period_start": str(b.period_start),
                    "period_end": str(b.period_end),
                    "total_seva_amount": float(b.total_seva_amount),
                    "transfer_status": b.transfer_status,
                    "transfer_reference": b.transfer_reference,
                }
                for b in batches
            ],
        }
        
    except Exception as e:
        logger.error(f"Batch listing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
