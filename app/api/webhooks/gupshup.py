"""
Gupshup WhatsApp Webhook Handler.
Receives inbound messages and status updates from Gupshup.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.user_service import UserService
from app.services.gupshup_service import GupshupService
from app.fsm.machine import FSMMachine

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/gupshup")
async def gupshup_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle incoming Gupshup webhook events.
    
    Gupshup sends different event types:
    - message: Inbound user message
    - message-event: Delivery status updates
    """
    try:
        # Parse request body
        content_type = request.headers.get("content-type", "")
        
        if "application/json" in content_type:
            payload = await request.json()
        else:
            # Gupshup sometimes sends form-urlencoded
            form_data = await request.form()
            payload = dict(form_data)
        
        logger.info(f"Gupshup webhook received: {payload}")
        
        # Extract event type
        event_type = payload.get("type", "message")
        
        if event_type == "message":
            await handle_inbound_message(payload, db)
        elif event_type == "message-event":
            await handle_message_status(payload, db)
        else:
            logger.warning(f"Unknown Gupshup event type: {event_type}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing Gupshup webhook: {e}", exc_info=True)
        # Return 200 to prevent Gupshup from retrying
        return {"status": "error", "message": str(e)}


async def handle_inbound_message(payload: dict, db: AsyncSession) -> None:
    """
    Process inbound user message.
    
    Payload structure:
    {
        "app": "AppName",
        "timestamp": 1234567890,
        "version": 2,
        "type": "message",
        "payload": {
            "id": "message_id",
            "source": "919876543210",
            "type": "text|button_reply|...",
            "payload": {
                "text": "Hello" | "id": "button_id", "title": "Button Title"
            },
            "sender": {
                "phone": "919876543210",
                "name": "User Name"
            }
        }
    }
    """
    message_payload = payload.get("payload", {})
    message_id = message_payload.get("id")
    sender_phone = message_payload.get("source")
    sender_name = message_payload.get("sender", {}).get("name")
    message_type = message_payload.get("type")
    content = message_payload.get("payload", {})
    
    if not sender_phone:
        logger.warning("No sender phone in message payload")
        return
    
    # Initialize services
    user_service = UserService(db)
    gupshup_service = GupshupService()
    
    # Get or create user
    user = await user_service.get_or_create_user(sender_phone, sender_name)
    
    # Check for duplicate message (idempotency)
    if await user_service.is_duplicate_message(user.id, message_id):
        logger.info(f"Duplicate message {message_id} ignored")
        return
    
    # Extract message content based on type
    if message_type == "text":
        text = content.get("text", "")
        button_payload = None
    elif message_type == "button_reply":
        text = content.get("title", "")
        button_payload = content.get("id")
    elif message_type == "quick_reply":
        text = content.get("text", "")
        button_payload = content.get("payload")
    else:
        logger.warning(f"Unknown message type: {message_type}")
        text = str(content)
        button_payload = None
    
    # Process through FSM
    fsm = FSMMachine(db, user, gupshup_service)
    await fsm.process_input(text, button_payload, message_id)


async def handle_message_status(payload: dict, db: AsyncSession) -> None:
    """
    Handle message delivery status updates.
    
    Status types: enqueued, failed, sent, delivered, read
    """
    event_payload = payload.get("payload", {})
    message_id = event_payload.get("id")
    status = event_payload.get("type")
    destination = event_payload.get("destination")
    
    logger.info(f"Message {message_id} to {destination}: {status}")
    
    # For now, just log status updates
    # In production, you might want to track delivery metrics
    if status == "failed":
        error = event_payload.get("payload", {}).get("reason", "Unknown")
        logger.error(f"Message {message_id} failed: {error}")
