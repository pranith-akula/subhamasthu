"""
Razorpay Webhook Handler.
Verifies signatures and processes payment events.
"""

import hmac
import hashlib
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.payment_service import PaymentService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Razorpay webhook events.
    
    Key events:
    - payment_link.paid: Payment completed via payment link
    - payment.captured: Payment captured
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        body_str = body.decode("utf-8")
        
        # Verify webhook signature
        signature = request.headers.get("X-Razorpay-Signature", "")
        
        if not verify_razorpay_signature(body_str, signature):
            logger.error("Invalid Razorpay webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse payload
        payload = await request.json()
        
        logger.info(f"Razorpay webhook received: {payload.get('event')}")
        
        # Extract event details
        event_type = payload.get("event")
        event_id = payload.get("event_id")  # For idempotency
        
        # Initialize payment service
        payment_service = PaymentService(db)
        
        # Check for duplicate event (idempotency)
        if await payment_service.is_duplicate_event(event_id):
            logger.info(f"Duplicate event {event_id} ignored")
            return {"status": "duplicate"}
        
        # Process based on event type
        if event_type == "payment_link.paid":
            await handle_payment_link_paid(payload, payment_service)
        elif event_type == "payment.captured":
            await handle_payment_captured(payload, payment_service)
        else:
            logger.info(f"Unhandled Razorpay event: {event_type}")
        
        return {"status": "ok"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Razorpay webhook: {e}", exc_info=True)
        # Return 200 to prevent excessive retries
        return {"status": "error", "message": str(e)}


def verify_razorpay_signature(payload: str, signature: str) -> bool:
    """
    Verify Razorpay webhook signature using HMAC SHA256.
    """
    if not settings.razorpay_webhook_secret:
        logger.warning("Razorpay webhook secret not configured")
        return True  # Skip verification in development
    
    expected_signature = hmac.new(
        settings.razorpay_webhook_secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


async def handle_payment_link_paid(payload: dict, payment_service: PaymentService) -> None:
    """
    Process payment_link.paid event.
    
    Payload contains:
    - payment_link: Payment link details with notes containing sankalp_id
    - payment: Payment details
    """
    event_id = payload.get("event_id")
    event_data = payload.get("payload", {})
    
    payment_link = event_data.get("payment_link", {}).get("entity", {})
    payment = event_data.get("payment", {}).get("entity", {})
    
    payment_link_id = payment_link.get("id")
    payment_id = payment.get("id")
    amount = payment.get("amount", 0) / 100  # Convert paise to rupees/dollars
    currency = payment.get("currency", "USD")
    
    # Extract sankalp_id from payment link notes
    notes = payment_link.get("notes", {})
    sankalp_id = notes.get("sankalp_id")
    
    if not sankalp_id:
        logger.error(f"No sankalp_id in payment link notes: {payment_link_id}")
        return
    
    # Process payment
    await payment_service.process_payment(
        event_id=event_id,
        sankalp_id=sankalp_id,
        payment_id=payment_id,
        amount=amount,
        currency=currency,
    )
    
    logger.info(f"Payment processed for sankalp {sankalp_id}: {amount} {currency}")


async def handle_payment_captured(payload: dict, payment_service: PaymentService) -> None:
    """
    Process payment.captured event (backup handler).
    """
    event_id = payload.get("event_id")
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    
    payment_id = payment.get("id")
    amount = payment.get("amount", 0) / 100
    currency = payment.get("currency", "USD")
    notes = payment.get("notes", {})
    sankalp_id = notes.get("sankalp_id")
    
    if not sankalp_id:
        logger.info(f"No sankalp_id in payment notes: {payment_id}")
        return
    
    await payment_service.process_payment(
        event_id=event_id,
        sankalp_id=sankalp_id,
        payment_id=payment_id,
        amount=amount,
        currency=currency,
    )
