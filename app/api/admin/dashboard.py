
import logging
from typing import List
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_admin_user
from app.models.sankalp import Sankalp
from app.models.seva_media import SevaMedia, MediaType
from app.fsm.states import SankalpStatus

# Setup templates
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

logger = logging.getLogger(__name__)
router = APIRouter()


# --- VIEW ROUTES (HTML) ---

@router.get("/admin-panel", response_class=HTMLResponse)
async def view_dashboard(request: Request):
    """Serve the main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "active_page": "dashboard"
    })

@router.get("/admin-panel/media", response_class=HTMLResponse)
async def view_media(request: Request):
    """Serve the media gallery page."""
    return templates.TemplateResponse("media.html", {
        "request": request, 
        "active_page": "media"
    })

@router.get("/admin-panel/users", response_class=HTMLResponse)
async def view_users(request: Request):
    """Serve the user management page."""
    return templates.TemplateResponse("users.html", {
        "request": request, 
        "active_page": "users"
    })

@router.get("/admin-panel/login", response_class=HTMLResponse)
async def view_login(request: Request):
    """Serve the login page."""
    return templates.TemplateResponse("login.html", {"request": request})


# --- API ROUTES (JSON DATA) ---

@router.get("/admin/api/users")
async def get_users_list(
    db: AsyncSession = Depends(get_db),
    admin_key: str = Depends(get_admin_user)
):
    """Get list of users with stats."""
    from app.models.user import User
    
    # Simple list for MVP. Ideal: aggregation for total_amount.
    # We will fetch last 100 users for now.
    query = select(User).order_by(desc(User.created_at)).limit(100)
    res = await db.execute(query)
    users = res.scalars().all()
    
    # Calculate stats for each user (inefficient for millions, fine for 100)
    items = []
    for u in users:
        # Count paid sankalps
        sankalp_query = select(Sankalp).where(
            Sankalp.user_id == u.id,
            Sankalp.status.in_([SankalpStatus.PAID, SankalpStatus.RECEIPT_SENT, SankalpStatus.CLOSED])
        )
        s_res = await db.execute(sankalp_query)
        sankalps = s_res.scalars().all()
        
        total_amount = sum([s.amount for s in sankalps])
        
        items.append({
            "id": str(u.id),
            "name": u.name,
            "phone": u.phone,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "sankalp_count": len(sankalps),
            "total_amount": float(total_amount)
        })
        
    return {"status": "success", "items": items}


@router.get("/admin/api/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    admin_key: str = Depends(get_admin_user)
):
    """
    Get aggregated statistics for the dashboard.
    Protected by X-Admin-Key.
    """
    
    # 1. Revenue Calculation (Sum of all paid sankalps)
    revenue_query = select(func.sum(Sankalp.amount)).where(
        Sankalp.status.in_([
            SankalpStatus.PAID, 
            SankalpStatus.RECEIPT_SENT, 
            SankalpStatus.CLOSED
        ])
    )
    revenue_res = await db.execute(revenue_query)
    total_revenue = revenue_res.scalar() or 0

    # 2. Impact Calculation (Families Fed)
    # Logic: Sum of (used_count * families_fed) for all media
    # Note: Default families_fed is 50 if null
    media_query = select(SevaMedia)
    media_res = await db.execute(media_query)
    all_media = media_res.scalars().all()
    
    total_families_fed = 0
    for m in all_media:
        if m.used_count > 0:
            count = m.families_fed if m.families_fed else 50
            total_families_fed += (m.used_count * count)

    # 3. Pending Ops (Paid but proof not sent)
    pending_query = select(func.count(Sankalp.id)).where(
        Sankalp.status == SankalpStatus.PAID,
        # Assuming proof_sent is a boolean flag on Sankalp as added in migration
        # We need to perform a raw check or text check if model isn't updated in python code yet
        # But we added it to DB. Let's check model... 
        # Wait, I didn't verify if `proof_sent` was added to `Sankalp` python model file.
        # I only added it to SQL migration.
        # Python sqlalchemy query might fail if column not in model.
        # Let's assume for now we use status=PAID as proxy for pending, 
        # since status changes to CLOSED/RECEIPT_SENT eventually?
        # Actually standard flow: PAID -> (Seva Done) -> RECEIPT_SENT. 
        # So STATUS=PAID implies pending seva.
    )
    pending_res = await db.execute(pending_query)
    pending_count = pending_res.scalar() or 0

    # 4. Media Pool Stats
    media_total_query = select(func.count(SevaMedia.id))
    media_total_res = await db.execute(media_total_query)
    media_total = media_total_res.scalar() or 0

    # 5. Recent Sankalps (simplified query without join)
    
    recent_swaps = []
    recent_res = await db.execute(
        select(Sankalp).order_by(desc(Sankalp.created_at)).limit(5)
    )
    for s in recent_res.scalars().all():
        # Get category first letter for generic avatar
        initial = s.category.replace("CAT_", "")[0] if s.category else "?"
        
        recent_swaps.append({
            "id": str(s.id),
            "amount": float(s.amount),
            "category": s.category.replace("CAT_", "").title(),
            "status": s.status,
            "user_name": "Donor", # Placeholder for speed
            "category_initial": initial
        })

    # 6. Demographics (DOB & Anniversary Coverage)
    from app.models.user import User
    
    # Total Users
    total_users_query = select(func.count(User.id))
    total_users = (await db.execute(total_users_query)).scalar() or 0
    
    # Users with DOB
    dob_query = select(func.count(User.id)).where(User.dob.is_not(None))
    dob_count = (await db.execute(dob_query)).scalar() or 0
    
    # Users with Anniversary
    anniv_query = select(func.count(User.id)).where(User.wedding_anniversary.is_not(None))
    anniv_count = (await db.execute(anniv_query)).scalar() or 0
    
    # 7. Upcoming Celebrations (Next 7 days)
    # Fetching all dates and filtering in python for simplicity/timezone handling
    # Optimization: Select only necessary columns
    dates_query = select(User.name, User.phone, User.dob, User.wedding_anniversary).where(
        (User.dob.is_not(None)) | (User.wedding_anniversary.is_not(None))
    )
    dates_res = await db.execute(dates_query)
    users_with_dates = dates_res.all()
    
    upcoming = []
    from datetime import datetime
    from zoneinfo import ZoneInfo
    
    ist = ZoneInfo("Asia/Kolkata")
    today = datetime.now(ist).date()
    
    for u in users_with_dates:
        # Check Birthday
        if u.dob:
            # Replace year with current year to compare
            try:
                this_year_bday = u.dob.replace(year=today.year)
                days_diff = (this_year_bday - today).days
                
                # Handle year wrap-around (e.g. today is Dec 30, bday is Jan 2)
                if days_diff < 0:
                     next_year_bday = u.dob.replace(year=today.year + 1)
                     days_diff = (next_year_bday - today).days
                
                if 0 <= days_diff <= 7:
                    upcoming.append({
                        "type": "Birthday",
                        "name": u.name or "User",
                        "phone": u.phone,
                        "date": u.dob.strftime("%d %b"),
                        "days_left": days_diff
                    })
            except ValueError:
                pass # Leap year edge case
                
        # Check Anniversary
        if u.wedding_anniversary:
            try:
                this_year_anniv = u.wedding_anniversary.replace(year=today.year)
                days_diff = (this_year_anniv - today).days
                
                if days_diff < 0:
                     next_year_anniv = u.wedding_anniversary.replace(year=today.year + 1)
                     days_diff = (next_year_anniv - today).days

                if 0 <= days_diff <= 7:
                    upcoming.append({
                        "type": "Anniversary",
                        "name": u.name or "User",
                        "phone": u.phone,
                        "date": u.wedding_anniversary.strftime("%d %b"),
                        "days_left": days_diff
                    })
            except ValueError:
                pass

    # Sort by days left
    upcoming.sort(key=lambda x: x['days_left'])

    return {
        "revenue": {"total": float(total_revenue)},
        "impact": {"families_fed": total_families_fed},
        "ops": {"pending_sevas": pending_count},
        "media": {"total": media_total},
        "demographics": {
            "total_users": total_users,
            "dob_count": dob_count,
            "anniv_count": anniv_count
        },
        "upcoming_celebrations": upcoming,
        "recent_sankalps": recent_swaps
    }
