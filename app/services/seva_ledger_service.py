"""
Seva Ledger Service - Annadanam tracking and batch management.
"""

import uuid
import logging
from datetime import date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.seva import SevaLedger, SevaBatch

logger = logging.getLogger(__name__)


class SevaLedgerService:
    """Service for managing seva ledger and batches."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_batch(
        self,
        period_start: date,
        period_end: date,
    ) -> SevaBatch:
        """
        Create a new seva batch for the given period.
        
        Groups all unbatched seva ledger entries from the period.
        """
        assert period_start is not None, "Period start is required"
        assert period_end is not None, "Period end is required"
        
        # Generate batch ID
        batch_id = f"SEVA-{period_start.strftime('%Y%m%d')}-{period_end.strftime('%Y%m%d')}"
        
        # Get all unbatched entries in the period
        result = await self.db.execute(
            select(SevaLedger)
            .where(SevaLedger.batch_id == None)  # noqa: E711
            .where(SevaLedger.created_at >= period_start)
            .where(SevaLedger.created_at <= period_end)
        )
        entries = list(result.scalars().all())
        
        if not entries:
            raise ValueError("No unbatched entries found for this period")
        
        # Calculate total seva amount
        total_seva = sum(entry.seva_amount for entry in entries)
        
        # Create batch
        batch = SevaBatch(
            batch_id=batch_id,
            period_start=period_start,
            period_end=period_end,
            total_seva_amount=total_seva,
            transfer_status="PENDING",
        )
        self.db.add(batch)
        
        # Update entries with batch ID
        for entry in entries:
            entry.batch_id = batch_id
        
        await self.db.flush()
        
        logger.info(f"Created batch {batch_id} with {len(entries)} entries, total: ${total_seva}")
        return batch
    
    async def mark_transferred(
        self,
        batch_id: str,
        transfer_reference: str,
    ) -> Optional[SevaBatch]:
        """Mark a batch as transferred with the reference."""
        result = await self.db.execute(
            select(SevaBatch).where(SevaBatch.batch_id == batch_id)
        )
        batch = result.scalar_one_or_none()
        
        if not batch:
            return None
        
        batch.transfer_reference = transfer_reference
        batch.transfer_status = "TRANSFERRED"
        
        logger.info(f"Batch {batch_id} marked as transferred: {transfer_reference}")
        return batch
    
    async def list_batches(self) -> List[SevaBatch]:
        """List all seva batches."""
        result = await self.db.execute(
            select(SevaBatch).order_by(SevaBatch.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_batch_summary(self, batch_id: str) -> Optional[dict]:
        """Get detailed summary of a batch."""
        result = await self.db.execute(
            select(SevaBatch).where(SevaBatch.batch_id == batch_id)
        )
        batch = result.scalar_one_or_none()
        
        if not batch:
            return None
        
        # Get entry count
        count_result = await self.db.execute(
            select(func.count(SevaLedger.id))
            .where(SevaLedger.batch_id == batch_id)
        )
        entry_count = count_result.scalar()
        
        return {
            "batch_id": batch.batch_id,
            "period_start": batch.period_start,
            "period_end": batch.period_end,
            "total_seva_amount": batch.total_seva_amount,
            "entry_count": entry_count,
            "transfer_status": batch.transfer_status,
            "transfer_reference": batch.transfer_reference,
        }
    
    async def get_total_seva_amount(self) -> Decimal:
        """Get total seva amount across all batches."""
        result = await self.db.execute(
            select(func.sum(SevaBatch.total_seva_amount))
        )
        total = result.scalar()
        return total or Decimal("0")
    
    async def get_pending_batches(self) -> List[SevaBatch]:
        """Get all pending (untransferred) batches."""
        result = await self.db.execute(
            select(SevaBatch)
            .where(SevaBatch.transfer_status == "PENDING")
            .order_by(SevaBatch.created_at)
        )
        return list(result.scalars().all())
