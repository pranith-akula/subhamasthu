"""
Payment Service - Razorpay payment processing and ledger management.
"""

import uuid
import logging
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sankalp import Sankalp
from app.models.payment import Payment
from app.models.seva import SevaLedger
from app.models.user import User
from app.fsm.states import SankalpStatus, ConversationState

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for processing Razorpay payments."""
    
    # Platform fee percentage (e.g., 20% for platform, 80% for seva)
    PLATFORM_FEE_PERCENT = Decimal("0.20")
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def is_duplicate_event(self, event_id: str) -> bool:
        """Check if Razorpay event has already been processed."""
        result = await self.db.execute(
            select(Payment).where(Payment.razorpay_event_id == event_id)
        )
        return result.scalar_one_or_none() is not None
    
    async def process_payment(
        self,
        event_id: str,
        sankalp_id: str,
        payment_id: str,
        amount: float,
        currency: str,
    ) -> bool:
        """
        Process a successful payment.
        
        1. Create payment record
        2. Update sankalp status
        3. Create seva ledger entry
        4. Trigger receipt generation
        5. Send closure message
        """
        try:
            sankalp_uuid = uuid.UUID(sankalp_id)
        except ValueError:
            logger.error(f"Invalid sankalp_id format: {sankalp_id}")
            return False
        
        # Get sankalp
        result = await self.db.execute(
            select(Sankalp).where(Sankalp.id == sankalp_uuid)
        )
        sankalp = result.scalar_one_or_none()
        
        if not sankalp:
            logger.error(f"Sankalp not found: {sankalp_id}")
            return False
        
        if sankalp.status == SankalpStatus.PAID.value:
            logger.info(f"Sankalp {sankalp_id} already marked as paid")
            return True
        
        # Create payment record
        payment = Payment(
            sankalp_id=sankalp.id,
            razorpay_payment_id=payment_id,
            razorpay_event_id=event_id,
            signature_verified=True,
            amount=Decimal(str(amount)),
            currency=currency,
        )
        self.db.add(payment)
        
        # Update sankalp status
        sankalp.status = SankalpStatus.PAID.value
        
        # Calculate platform fee and seva amount
        total_amount = Decimal(str(amount))
        platform_fee = total_amount * self.PLATFORM_FEE_PERCENT
        seva_amount = total_amount - platform_fee
        
        # Create seva ledger entry
        ledger_entry = SevaLedger(
            sankalp_id=sankalp.id,
            platform_fee=platform_fee,
            seva_amount=seva_amount,
        )
        self.db.add(ledger_entry)
        
        await self.db.flush()
        
        logger.info(f"Payment processed for sankalp {sankalp_id}: ${amount}")
        
        # Get user and send closure
        await self._trigger_post_payment_flow(sankalp)
        
        return True
    
    async def _trigger_post_payment_flow(self, sankalp: Sankalp) -> None:
        """Trigger post-payment actions (receipt, closure message)."""
        from app.services.sankalp_service import SankalpService
        from app.services.user_service import UserService
        from app.services.receipt_service import ReceiptService
        
        # Get user
        user_result = await self.db.execute(
            select(User).where(User.id == sankalp.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            logger.error(f"User not found for sankalp {sankalp.id}")
            return
        
        # Send closure message (Punya Stage)
        sankalp_service = SankalpService(self.db)
        await sankalp_service.send_punya_completion(user, sankalp)
        
        # Generate and send receipt
        receipt_service = ReceiptService(self.db)
        receipt_url = await receipt_service.generate_and_send_receipt(user, sankalp)
        
        if receipt_url:
            sankalp.receipt_url = receipt_url
            sankalp.status = SankalpStatus.RECEIPT_SENT.value
        
        # Update user state and cooldown
        user_service = UserService(self.db)
        await user_service.update_user_state(user, ConversationState.COOLDOWN)
        await user_service.set_last_sankalp(user)
        
        # Final status
        sankalp.status = SankalpStatus.CLOSED.value
        
        logger.info(f"Post-payment flow complete for sankalp {sankalp.id}")
