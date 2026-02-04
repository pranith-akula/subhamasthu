"""
Gupshup Service - WhatsApp messaging via Gupshup API.
"""

import logging
from typing import Optional, List, Dict, Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Gupshup API base URL
GUPSHUP_API_URL = "https://api.gupshup.io/wa/api/v1/msg"


class GupshupService:
    """Service for sending WhatsApp messages via Gupshup."""
    
    def __init__(self):
        self.api_key = settings.gupshup_api_key
        self.app_name = settings.gupshup_app_name
        self.source_number = settings.gupshup_source_number
    
    async def send_text_message(
        self,
        phone: str,
        message: str,
    ) -> Optional[str]:
        """
        Send a plain text message.
        
        Returns message ID on success, None on failure.
        """
        payload = {
            "channel": "whatsapp",
            "source": self.source_number,
            "destination": phone,
            "message": {
                "type": "text",
                "text": message,
            },
            "src.name": self.app_name,
        }
        
        return await self._send_message(payload)
    
    async def send_button_message(
        self,
        phone: str,
        body_text: str,
        buttons: List[Dict[str, str]],
        header: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send an interactive button message.
        
        Args:
            phone: Recipient phone number
            body_text: Main message body
            buttons: List of buttons, each with {id: str, title: str}
            header: Optional header text
            footer: Optional footer text
        
        Returns message ID on success, None on failure.
        """
        # Build interactive message structure
        interactive = {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": btn["id"],
                            "title": btn["title"][:20],  # Max 20 chars
                        }
                    }
                    for btn in buttons[:3]  # Max 3 buttons
                ]
            }
        }
        
        if header:
            interactive["header"] = {"type": "text", "text": header}
        
        if footer:
            interactive["footer"] = {"text": footer}
        
        payload = {
            "channel": "whatsapp",
            "source": self.source_number,
            "destination": phone,
            "message": {
                "type": "interactive",
                "interactive": interactive,
            },
            "src.name": self.app_name,
        }
        
        return await self._send_message(payload)
    
    async def send_list_message(
        self,
        phone: str,
        body_text: str,
        button_text: str,
        sections: List[Dict[str, Any]],
        header: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send an interactive list message with sections.
        
        Args:
            phone: Recipient phone number
            body_text: Main message body
            button_text: Text on the list button
            sections: List of sections with rows
            header: Optional header text
            footer: Optional footer text
        """
        interactive = {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": button_text,
                "sections": sections,
            }
        }
        
        if header:
            interactive["header"] = {"type": "text", "text": header}
        
        if footer:
            interactive["footer"] = {"text": footer}
        
        payload = {
            "channel": "whatsapp",
            "source": self.source_number,
            "destination": phone,
            "message": {
                "type": "interactive",
                "interactive": interactive,
            },
            "src.name": self.app_name,
        }
        
        return await self._send_message(payload)
    
    async def send_template_message(
        self,
        phone: str,
        template_id: str,
        params: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Send a pre-approved HSM template message.
        
        Args:
            phone: Recipient phone number
            template_id: Gupshup template ID
            params: Template parameter values
        """
        template_data = {
            "id": template_id,
        }
        
        if params:
            template_data["params"] = params
        
        payload = {
            "channel": "whatsapp",
            "source": self.source_number,
            "destination": phone,
            "message": {
                "type": "template",
                "template": template_data,
            },
            "src.name": self.app_name,
        }
        
        return await self._send_message(payload)
    
    async def send_document(
        self,
        phone: str,
        document_url: str,
        filename: str,
        caption: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send a document (PDF, etc).
        
        Args:
            phone: Recipient phone number
            document_url: Public URL of the document
            filename: Display filename
            caption: Optional caption
        """
        document = {
            "link": document_url,
            "filename": filename,
        }
        
        if caption:
            document["caption"] = caption
        
        payload = {
            "channel": "whatsapp",
            "source": self.source_number,
            "destination": phone,
            "message": {
                "type": "document",
                "document": document,
            },
            "src.name": self.app_name,
        }
        
        return await self._send_message(payload)
    
    async def _send_message(self, payload: dict) -> Optional[str]:
        """
        Send message to Gupshup API with retry logic.
        """
        headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    GUPSHUP_API_URL,
                    json=payload,
                    headers=headers,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "submitted":
                        message_id = data.get("messageId")
                        logger.info(f"Message sent: {message_id}")
                        return message_id
                    else:
                        logger.error(f"Gupshup error: {data}")
                        return None
                else:
                    logger.error(f"Gupshup HTTP error: {response.status_code} {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error("Gupshup request timeout")
            return None
        except Exception as e:
            logger.error(f"Gupshup send error: {e}", exc_info=True)
            return None
