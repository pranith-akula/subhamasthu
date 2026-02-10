"""
Razorpay Webhook Handler.
Verifies signatures and processes payment events.
"""

import hmac
import hashlib
import logging
import uuid
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
        elif event_type == "subscription.charged":
            await handle_subscription_charged(payload, payment_service)
        elif event_type == "payment_link.expired":
            await handle_payment_link_expired(payload, payment_service, db)
        elif event_type == "payment.failed":
            await handle_payment_failed(payload, payment_service, db)
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
    
    # Record Engagement for the user
    try:
        from sqlalchemy import select
        from app.models.sankalp import Sankalp
        from app.models.user import User
        from app.services.user_service import UserService
        
        # We need a new session or use the existing one if available in payment_service
        # For simplicity, we can fetch user by sankalp_id if not already in session
        db = payment_service.db
        sankalp_res = await db.execute(select(Sankalp).where(Sankalp.id == uuid.UUID(sankalp_id)))
        sankalp = sankalp_res.scalar_one_or_none()
        if sankalp:
            user_res = await db.execute(select(User).where(User.id == sankalp.user_id))
            user = user_res.scalar_one_or_none()
            if user:
                user_service = UserService(db)
                await user_service.record_engagement(user)
    except Exception as e:
        logger.warning(f"Failed to record engagement for payment: {e}")

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


async def handle_subscription_charged(payload: dict, payment_service: PaymentService) -> None:
    """
    Process subscription.charged event.
    Recurring payment successful.
    """
    event_id = payload.get("event_id")
    event_data = payload.get("payload", {})
    
    subscription = event_data.get("subscription", {}).get("entity", {})
    payment = event_data.get("payment", {}).get("entity", {})
    
    subscription_id = subscription.get("id")
    payment_id = payment.get("id")
    amount = payment.get("amount", 0) / 100
    currency = payment.get("currency", "USD")
    
    # Extract sankalp_id from subscription notes
    notes = subscription.get("notes", {})
    sankalp_id = notes.get("sankalp_id")
    
    if not sankalp_id:
        # Fallback: Check payment notes
        sankalp_id = payment.get("notes", {}).get("sankalp_id")
    
    if not sankalp_id:
        logger.error(f"No sankalp_id in subscription {subscription_id} notes")
        return

    logger.info(f"Subscription {subscription_id} charged for sankalp {sankalp_id}")

    # Process payment (Update Sankalp Status)
    # Note: For recurring months, ideally we create a NEW Sankalp record.
    # But for MVP, we just confirm the current one is paid (or re-paid).
    await payment_service.process_payment(
        event_id=event_id,
        sankalp_id=sankalp_id,
        payment_id=payment_id,
        amount=amount,
        currency=currency,
    )


async def handle_payment_link_expired(
    payload: dict,
    payment_service: PaymentService,
    db: AsyncSession,
) -> None:
    """
    Handle payment_link.expired event.
    
    When user doesn't complete payment, we:
    1. Mark sankalp as expired
    2. Return user to DAILY_PASSIVE state
    3. Optionally notify user
    """
    from sqlalchemy import select
    from app.models.sankalp import Sankalp
    from app.models.user import User
    from app.fsm.states import SankalpStatus, ConversationState
    from app.services.user_service import UserService
    from app.services.meta_whatsapp_service import MetaWhatsappService
    
    event_data = payload.get("payload", {})
    payment_link = event_data.get("payment_link", {}).get("entity", {})
    
    payment_link_id = payment_link.get("id")
    notes = payment_link.get("notes", {})
    sankalp_id = notes.get("sankalp_id")
    
    if not sankalp_id:
        logger.info(f"No sankalp_id in expired payment link: {payment_link_id}")
        return
    
    try:
        sankalp_uuid = uuid.UUID(sankalp_id)
    except ValueError:
        logger.error(f"Invalid sankalp_id format: {sankalp_id}")
        return
    
    # Get sankalp
    result = await db.execute(
        select(Sankalp).where(Sankalp.id == sankalp_uuid)
    )
    sankalp = result.scalar_one_or_none()
    
    if not sankalp:
        logger.error(f"Sankalp not found for expired link: {sankalp_id}")
        return
    
    # Mark sankalp as expired
    sankalp.status = SankalpStatus.EXPIRED.value if hasattr(SankalpStatus, 'EXPIRED') else "EXPIRED"
    
    # Get user
    user_result = await db.execute(
        select(User).where(User.id == sankalp.user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if user:
        # Return user to passive state
        user_service = UserService(db)
        await user_service.update_user_state(user, ConversationState.DAILY_PASSIVE)
        
        # Send gentle reminder message
        whatsapp = MetaWhatsappService()
        message = """🙏 నమస్కారం!

మీ సంకల్ప లింక్ గడువు ముగిసింది.

చింతించకండి - మీ తదుపరి శుభ దినం రోజు మళ్ళీ అవకాశం వస్తుంది.

అప్పటివరకు, మీకు ప్రతిరోజూ రాశిఫలాలు వస్తూనే ఉంటాయి.

🙏 శుభమస్తు!"""
        
        await whatsapp.send_text_message(
            phone=user.phone,
            message=message,
        )
    
    await db.commit()
    logger.info(f"Payment link expired for sankalp {sankalp_id}, user returned to passive")


async def handle_payment_failed(
    payload: dict,
    payment_service: PaymentService,
    db: AsyncSession,
) -> None:
    """
    Handle payment.failed event.
    Notify user and suggest retry with same link.
    """
    from sqlalchemy import select
    from app.models.sankalp import Sankalp
    from app.models.user import User
    from app.services.meta_whatsapp_service import MetaWhatsappService
    
    event_data = payload.get("payload", {})
    payment = event_data.get("payment", {}).get("entity", {})
    
    payment_id = payment.get("id")
    notes = payment.get("notes", {})
    sankalp_id = notes.get("sankalp_id")
    
    if not sankalp_id:
        logger.info(f"No sankalp_id in failed payment: {payment_id}")
        return
        
    try:
        sankalp_uuid = uuid.UUID(sankalp_id)
    except ValueError:
        logger.error(f"Invalid sankalp_id format: {sankalp_id}")
        return
        
    # Get sankalp
    result = await db.execute(
        select(Sankalp).where(Sankalp.id == sankalp_uuid)
    )
    sankalp = result.scalar_one_or_none()
    
    if not sankalp:
        logger.error(f"Sankalp not found for failed payment: {sankalp_id}")
        return

    # Check for short_url
    short_url = None
    if sankalp.razorpay_ref and isinstance(sankalp.razorpay_ref, dict):
         short_url = sankalp.razorpay_ref.get("short_url")
         
    if not short_url:
        logger.warning(f"No short_url found for sankalp {sankalp_id}, cannot send retry link")
        return

    # Get user
    user_result = await db.execute(
        select(User).where(User.id == sankalp.user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if user:
        # Send failure notification
        whatsapp = MetaWhatsappService()
        message = f"⚠️ **చెల్లింపు విఫలమైంది** (Payment Failed)\n\nదయచేసి మళ్ళీ ప్రయత్నించండి:\n{short_url}\n\nమీకు ఏవైనా సమస్యలు ఉంటే, దయచేసి కాసేపటి తర్వాత ప్రయత్నించండి."

        await whatsapp.send_text_message(
            phone=user.phone,
            message=message,
        )
        
    logger.info(f"Sent payment failure notification for sankalp {sankalp_id}")

