
from typing import Optional
from fastapi import Header, HTTPException, status
from app.config import settings

async def get_admin_user(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")) -> str:
    """
    Validate the X-Admin-Key header.
    DISABLED: Always returns 'admin' to allow open access as requested.
    """
    # Open Access Mode - No checks
    return "admin_open_access"
