"""
Meta WhatsApp Service - Direct integration with Meta Cloud API.
Drop-in replacement for GupshupService.
"""

import logging
from typing import Optional, List, Dict, Any
import httpx

from app.config import settings

logger = logging.getLogger(__name__)

class MetaWhatsappService:
    """Service for sending WhatsApp messages via Meta Cloud API."""
    
    def __init__(self):
        self.api_key = settings.meta_access_token
        self.phone_number_id = settings.meta_phone_number_id
        self.api_version = "v18.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
    
    async def _send_request(self, payload: Dict[str, Any]) -> Optional[str]:
        """Send raw request to Meta API."""
        if not self.api_key or not self.phone_number_id:
            logger.error("Meta API credentials not configured")
            return None
            
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    json=payload,
                    headers=self.headers,
                    timeout=10.0
                )
                
                if response.status_code in [200, 201]:
                    data = response.json()
                    # Meta specific: messages are in ['messages'][0]['id']
                    return data.get("messages", [{}])[0].get("id")
                else:
                    logger.error(f"Meta API Error {response.status_code}: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Meta API Exception: {e}")
            return None

    async def send_text_message(
        self,
        phone: str,
        message: str,
    ) -> Optional[str]:
        """Send a plain text message."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"preview_url": False, "body": message}
        }
        return await self._send_request(payload)
    
    async def send_button_message(
        self,
        phone: str,
        body_text: str,
        buttons: List[Dict[str, str]],
        header: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> Optional[str]:
        """Send an interactive button message."""
        # Meta allows max 3 buttons
        meta_buttons = []
        for btn in buttons[:3]:
            meta_buttons.append({
                "type": "reply",
                "reply": {
                    "id": btn["id"],
                    "title": btn["title"][:20]  # Max 20 chars
                }
            })
            
        interactive = {
            "type": "button",
            "body": {"text": body_text},
            "action": {"buttons": meta_buttons}
        }
        
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}
            
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "interactive",
            "interactive": interactive
        }
        
        return await self._send_request(payload)
    
    async def send_button_message_with_menu(
        self,
        phone: str,
        body_text: str,
        buttons: List[Dict[str, str]],
        header: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send button message with automatic 'Main Menu' option.
        
        - If <= 2 buttons: Appends 'Menu' button
        - If 3 buttons: Adds footer hint 'Type 0 for menu'
        
        This gives users a consistent way to exit any flow.
        """
        MENU_BUTTON = {"id": "CMD_MAIN_MENU", "title": "🏠 Menu"}
        
        # Determine how to add menu option
        if len(buttons) <= 2:
            # Add Menu as 3rd button
            buttons_with_menu = buttons + [MENU_BUTTON]
            final_footer = footer
        else:
            # Can't fit button - add hint to footer
            buttons_with_menu = buttons[:3]
            hint = "Type 0 for menu"
            final_footer = f"{footer} | {hint}" if footer else hint
        
        return await self.send_button_message(
            phone=phone,
            body_text=body_text,
            buttons=buttons_with_menu,
            header=header,
            footer=final_footer,
        )

    async def send_list_message(
        self,
        phone: str,
        body_text: str,
        button_text: str,
        sections: List[Dict[str, Any]],
        header: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> Optional[str]:
        """Send an interactive list message."""
        # Meta strict format for sections
        # rows must have 'id' and 'title' (max 24 chars)
        
        interactive = {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": button_text[:20],
                "sections": sections
            }
        }
        
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}
            
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "interactive",
            "interactive": interactive
        }
        
        return await self._send_request(payload)
        
    async def send_template_message(
        self,
        phone: str,
        template_id: str,
        params: Optional[List[str]] = None, # List of strings
        media_url: Optional[str] = None,
        media_type: Optional[str] = None,
        language: str = "te" # Default to Telugu
    ) -> Optional[str]:
        """Send a template message (HSM)."""
        
        components = []
        
        # 1. Header (Media)
        if media_url and media_type:
            header_comp = {
                "type": "header",
                "parameters": [
                    {
                        "type": media_type, # image, video, document
                        media_type: {"link": media_url}
                    }
                ]
            }
            components.append(header_comp)
            
        # 2. Body (Params)
        if params:
            body_params = []
            for p in params:
                body_params.append({
                    "type": "text",
                    "text": str(p)
                })
            
            components.append({
                "type": "body",
                "parameters": body_params
            })
            
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_id,
                "language": {"code": language},
                "components": components
            }
        }
        
        return await self._send_request(payload)
    
    async def send_image_message(
        self,
        phone: str,
        image_url: str,
        caption: Optional[str] = None,
    ) -> Optional[str]:
        """Send an image message."""
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "image",
            "image": {"link": image_url}
        }
        if caption:
            payload["image"]["caption"] = caption
            
        return await self._send_request(payload)

    async def send_video_message(
        self,
        phone: str,
        video_url: str,
        caption: Optional[str] = None,
    ) -> Optional[str]:
        """Send a video message."""
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "video",
            "video": {"link": video_url}
        }
        if caption:
            payload["video"]["caption"] = caption
            
        return await self._send_request(payload)


    async def send_cta_url_message(
        self,
        phone: str,
        body_text: str,
        button_text: str,
        url: str,
        header: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send an interactive CTA URL button message.
        Note: This message type allows ONE button that opens a website/app.
        """
        interactive = {
            "type": "cta_url",
            "body": {"text": body_text},
            "action": {
                "name": "cta_url",
                "parameters": {
                    "display_text": button_text[:20],
                    "url": url
                }
            }
        }
        
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}
            
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "interactive",
            "interactive": interactive
        }
        
        return await self._send_request(payload)
