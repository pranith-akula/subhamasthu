"""
Impact API Router - Public endpoint for transparency metrics.

Security:
- Read-only
- Redis cached (5 min)
- Rate limited
- No internal IDs exposed
- No revenue shown (meals > money)
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.impact_service import ImpactService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Impact"])

# Simple in-memory rate limiting (per IP)
_rate_limit_cache: Dict[str, float] = {}
RATE_LIMIT_SECONDS = 5  # Min seconds between requests per IP


async def check_rate_limit(request: Request) -> None:
    """Basic IP-based rate limiting."""
    import time
    
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    last_request = _rate_limit_cache.get(client_ip, 0)
    if current_time - last_request < RATE_LIMIT_SECONDS:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a moment."
        )
    
    _rate_limit_cache[client_ip] = current_time


@router.get("/impact")
async def get_global_impact(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Get global impact metrics.
    
    Public endpoint showing collective seva impact.
    Only verified executions are counted.
    
    Returns:
        - total_meals: All-time meals served
        - this_month_meals: Meals this calendar month
        - this_week_meals: Meals this ISO week
        - active_devotees: Unique donors this month
        - cities: List of temple cities
        - last_seva_date: Date of most recent verified seva
    """
    # Rate limit check
    await check_rate_limit(request)
    
    try:
        service = ImpactService(db)
        impact = await service.get_global_impact(use_cache=True)
        
        return JSONResponse(
            content=impact,
            headers={
                "Cache-Control": "public, max-age=300",  # 5 min browser cache
                "X-Content-Type-Options": "nosniff",
            }
        )
    except Exception as e:
        logger.error(f"Impact API error: {e}")
        return JSONResponse(
            content={"error": "Unable to load impact data"},
            status_code=500
        )


@router.get("/impact/me")
async def get_personal_impact(
    phone: str,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Get personal impact for a user (by phone).
    
    Returns:
        - lifetime_meals: Total meals from user's verified sevas
        - sankalp_count: Number of completed sankalps
    """
    from app.services.user_service import UserService
    
    try:
        user_service = UserService(db)
        user = await user_service.get_or_create_user(phone)
        
        if not user:
            return JSONResponse(
                content={"lifetime_meals": 0, "sankalp_count": 0}
            )
        
        service = ImpactService(db)
        impact = await service.get_user_impact(user.id)
        
        return JSONResponse(content=impact)
    except Exception as e:
        logger.error(f"Personal impact API error: {e}")
        return JSONResponse(
            content={"error": "Unable to load personal impact"},
            status_code=500
        )
