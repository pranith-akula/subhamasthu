"""
Meta WhatsApp Webhook Handler.
Receives inbound messages and status updates from Meta Cloud API.
"""

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.services.user_service import UserService
from app.services.meta_whatsapp_service import MetaWhatsappService
from app.fsm.machine import FSMMachine

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/meta")
async def meta_webhook_verification(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge"),
):
    """
    Handle Meta Webhook Verification Challenge.
    """
    if mode == "subscribe" and token == settings.meta_webhook_verify_token:
        logger.info("Meta Webhook Verified Successfully")
        return int(challenge)
    
    logger.warning(f"Meta Webhook Verification Failed: token={token}")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/meta")
async def meta_webhook_event(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle incoming Meta webhook events (Messages & Statuses).
    """
    try:
        payload = await request.json()
        logger.info(f"Meta webhook received: {payload}")
        
        # Parse entry
        entry = payload.get("entry", [])
        if not entry:
            return {"status": "ok"}
            
        changes = entry[0].get("changes", [])
        if not changes:
            return {"status": "ok"}
            
        value = changes[0].get("value", {})
        
        # Check if it's a message or status
        if "messages" in value:
            await handle_inbound_message(value, db)
        elif "statuses" in value:
            # TODO: Handle delivery receipts if needed
            pass
            
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error processing Meta webhook: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/meta/delete")
async def meta_delete_callback(request: Request):
    """
    Handle Meta Data Deletion Callback.
    Required for App Review.
    """
    # Parse signed_request if needed, but for now just return confirmation
    from uuid import uuid4
    confirmation_code = str(uuid4())
    
    logger.info(f"Meta Data Deletion Request received. Generated code: {confirmation_code}")
    
    # URL where user can track deletion status (Mock for compliance)
    status_url = f"https://subhamasthu.com/deletion-status?id={confirmation_code}"
    
    return {
        "url": status_url,
        "confirmation_code": confirmation_code
    }


async def handle_inbound_message(value: Dict[str, Any], db: AsyncSession) -> None:
    """Process inbound user message from Meta format."""
    contacts = value.get("contacts", [])
    messages = value.get("messages", [])
    
    if not messages:
        return
        
    message = messages[0]
    sender_phone = message.get("from") # Meta uses 'from' for phone
    sender_name = contacts[0].get("profile", {}).get("name") if contacts else "Unknown"
    msg_type = message.get("type")
    msg_id = message.get("id")
    
    if not sender_phone:
        logger.warning("No sender phone in message payload")
        return
        
    # Extract text/payload
    text = None
    button_payload = None
    
    if msg_type == "text":
        text = message.get("text", {}).get("body")
    elif msg_type == "interactive":
        interactive = message.get("interactive", {})
        int_type = interactive.get("type")
        
        if int_type == "button_reply":
            button_payload = interactive.get("button_reply", {}).get("id")
            text = interactive.get("button_reply", {}).get("title") # Optional: treat title as text
        elif int_type == "list_reply":
            button_payload = interactive.get("list_reply", {}).get("id")
            text = interactive.get("list_reply", {}).get("title")
    elif msg_type == "button": # Legacy button template response
        button_payload = message.get("button", {}).get("payload")
        text = message.get("button", {}).get("text")
        
    # Trigger FSM
    whatsapp_service = MetaWhatsappService()
    user_service = UserService(db)
    
    # Get or create user
    user = await user_service.get_or_create_user(
        phone=sender_phone,
        name=sender_name
    )
    
    # Initialize State Machine
    fsm = FSMMachine(
        db=db,
        user=user,
        whatsapp=whatsapp_service
    )
    
    # Process Input
    await fsm.process_input(
        text=text,
        button_payload=button_payload,
        message_id=msg_id
    )
