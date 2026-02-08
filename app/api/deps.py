from typing import Optional
from fastapi import Header, HTTPException, status, Cookie, Request
from fastapi.responses import RedirectResponse
from app.config import settings

async def get_admin_user(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    admin_key_cookie: Optional[str] = Cookie(None, alias="admin_key")
) -> str:
    """
    Validate the Admin Key from Header or Cookie.
    Returns the key if valid, raises 401 otherwise.
    """
    key = x_admin_key or admin_key_cookie
    
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Admin Password",
        )
    
    # Check against settings first
    valid_key = getattr(settings, "admin_api_key", None)
    
    if not valid_key or key != valid_key:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Admin Password",
        )
        
    return key

async def get_admin_user_html(
    request: Request,
    admin_key: Optional[str] = Cookie(None, alias="admin_key")
) -> str:
    """
    Validate Admin Key for HTML pages.
    Redirects to login if invalid.
    """
    valid_key = getattr(settings, "admin_api_key", None)
    
    if not admin_key or not valid_key or admin_key != valid_key:
        # Redirect to login
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin-panel/login"},
        )
        
    return admin_key
