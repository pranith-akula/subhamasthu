"""
Seva Proof Worker - Send proof to yesterday's donors at 11am.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.database import get_db_session
from app.services.seva_proof_service import SevaProofService

logger = logging.getLogger(__name__)


async def send_seva_proof_job():
    """
    Send seva proof to yesterday's donors.
    
    Should be scheduled to run at 11:00 AM IST daily.
    """
    logger.info(f"Starting seva proof job at {datetime.now()}")
    
    async with get_db_session() as db:
        service = SevaProofService(db)
        
        sent = await service.send_proof_to_yesterday_donors()
        
        logger.info(f"Seva proof job completed. Sent to {sent} donors.")
        
        return sent


def run_seva_proof_worker():
    """Entry point for cron/scheduler."""
    return asyncio.run(send_seva_proof_job())


if __name__ == "__main__":
    # Manual run
    logging.basicConfig(level=logging.INFO)
    run_seva_proof_worker()
