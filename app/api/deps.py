
from typing import Optional
from fastapi import Header, HTTPException, status
from app.config import settings

async def get_admin_user(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")) -> str:
    """
    Validate the X-Admin-Key header (Password).
    Returns the key if valid, raises 401 otherwise.
    """
    if not x_admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Admin Password",
        )
    
    # Check against settings first
    valid_key = getattr(settings, "admin_api_key", None)
    
    # HARDCODED FALLBACK (User requested simple password)
    MASTER_KEY = "Zilla831"
    
    if x_admin_key == MASTER_KEY:
        return x_admin_key
    
    if x_admin_key != valid_key:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Admin Password",
        )
        
    return x_admin_key
