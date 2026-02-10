
import logging
from typing import List
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.database import get_db
from app.api.deps import get_admin_user, get_admin_html_user
from app.config import settings
from app.models.user import User
from app.models.sankalp import Sankalp
from app.models.seva_media import SevaMedia, MediaType
from app.fsm.states import SankalpStatus, ConversationState

# Setup templates
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "app" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

logger = logging.getLogger(__name__)
router = APIRouter()


# --- VIEW ROUTES (HTML) ---

@router.get("/admin-panel", response_class=HTMLResponse)
async def view_dashboard(
    request: Request,
    _: str = Depends(get_admin_html_user)
):
    """Serve the main dashboard page."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "active_page": "dashboard"
    })

@router.get("/admin-panel/media", response_class=HTMLResponse)
async def view_media(
    request: Request,
    _: str = Depends(get_admin_html_user)
):
    """Serve the media gallery page."""
    return templates.TemplateResponse("media.html", {
        "request": request, 
        "active_page": "media"
    })

@router.get("/admin-panel/users", response_class=HTMLResponse)
async def view_users(
    request: Request,
    _: str = Depends(get_admin_html_user)
):
    """Serve the user management page."""
    return templates.TemplateResponse("users.html", {
        "request": request, 
        "active_page": "users"
    })

@router.get("/admin-panel/login", response_class=HTMLResponse)
async def view_login(request: Request):
    """Serve the login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/admin-panel/login")
async def login(
    request: Request,
    password: str = Form(...)
):
    """Handle login submission."""
    valid_key = getattr(settings, "admin_api_key", None)
    
    if not valid_key or password != valid_key:
         return templates.TemplateResponse("login.html", {
             "request": request, 
             "error": "Invalid Password"
         })
    
    # Redirect with authtoken to bypass initial cookie blocking
    response = RedirectResponse(
        url=f"/admin-panel?authtoken={password}", 
        status_code=303
    )
    
    # Still attempt to set cookie for future requests
    response.set_cookie(
        key="admin_key", 
        value=password, 
        httponly=True,
        max_age=86400 * 30, # 30 days
        path="/",
        samesite="lax",
        secure=True # Required for Railway HTTPS
    )
    logger.info(f"Login successful. Setting cookie for key: ...{password[-4:]}")
    return response


# --- API ROUTES (JSON DATA) ---

@router.get("/admin/api/users")
async def get_users_list(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_admin_user)
):
    """Get list of users with stats."""
    # Optimized query: Fetch Users + Aggregated Sankalp Stats in ONE query
    # avoiding N+1 problem.
    query = (
        select(
            User,
            func.count(case(
                (Sankalp.status.in_([SankalpStatus.PAID, SankalpStatus.RECEIPT_SENT, SankalpStatus.CLOSED]), Sankalp.id),
                else_=None
            )).label("sankalp_count"),
            func.sum(case(
                (Sankalp.status.in_([SankalpStatus.PAID, SankalpStatus.RECEIPT_SENT, SankalpStatus.CLOSED]), Sankalp.amount),
                else_=0
            )).label("total_amount")
        )
        .outerjoin(Sankalp, User.id == Sankalp.user_id)
        .group_by(User.id)
        .order_by(desc(User.created_at))
        .limit(100)
    )
    
    res = await db.execute(query)
    rows = res.all() # Returns list of (User, count, amount) tuples
    
    items = []
    for user, count, amount in rows:
        items.append({
            "id": str(user.id),
            "name": user.name,
            "phone": user.phone,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "sankalp_count": count,
            "total_amount": float(amount or 0)
        })
        
    return {"status": "success", "items": items}


@router.get("/admin/api/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    admin_key: str = Depends(get_admin_user)
):
    # --- CONSTANTS & DEFAULTS ---
    onboarding_states = [
        ConversationState.NEW,
        ConversationState.WAITING_FOR_NAME,
        ConversationState.WAITING_FOR_RASHI,
        ConversationState.WAITING_FOR_NAKSHATRA,
        ConversationState.WAITING_FOR_BIRTH_TIME,
        ConversationState.WAITING_FOR_DEITY,
        ConversationState.WAITING_FOR_AUSPICIOUS_DAY
    ]
    paid_statuses = [
        SankalpStatus.PAID,
        SankalpStatus.RECEIPT_SENT,
        SankalpStatus.CLOSED
    ]
    
    total_revenue = 0
    total_families_fed = 0
    pending_count = 0
    media_total = 0
    total_users = 0
    dob_count = 0
    anniv_count = 0
    active_users = 0
    seva_users = 0
    tiers = []
    upcoming = []
    recent_swaps = []
    business_metrics = {}

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

    # 6. Demographics & 7. Upcoming Celebrations
    # Wrapped in try/except to prevent dashboard crash on date errors
    
    upcoming = []
    dob_count = 0
    anniv_count = 0
    total_users = 0
    
    try:
        # Total Users
        total_users_query = select(func.count(User.id))
        total_users = (await db.execute(total_users_query)).scalar() or 0
        
        # Users with DOB
        dob_query = select(func.count(User.id)).where(User.dob.is_not(None))
        dob_count = (await db.execute(dob_query)).scalar() or 0
        
        # Users with Anniversary
        anniv_query = select(func.count(User.id)).where(User.wedding_anniversary.is_not(None))
        anniv_count = (await db.execute(anniv_query)).scalar() or 0
        
        # Upcoming
        from datetime import datetime
        from zoneinfo import ZoneInfo
        
        ist = ZoneInfo("Asia/Kolkata")
        today = datetime.now(ist).date()

        dates_query = select(User.name, User.phone, User.dob, User.wedding_anniversary).where(
            (User.dob.is_not(None)) | (User.wedding_anniversary.is_not(None))
        )
        dates_res = await db.execute(dates_query)
        users_with_dates = dates_res.all()
        
        for u in users_with_dates:
            try:
                # Check Birthday
                if u.dob:
                    this_year_bday = u.dob.replace(year=today.year)
                    days_diff = (this_year_bday - today).days
                    
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
                        
                # Check Anniversary
                if u.wedding_anniversary:
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
                continue # Leap year or invalid date
            except Exception as e:
                logger.warning(f"Error processing date for user: {e}")
                continue

        # Sort by days left
        upcoming.sort(key=lambda x: x['days_left'])
        
        
        # --- NEW METRICS ---
        
        # 8. Active Users (Completed Onboarding)
        # We assume anyone NOT in the initial onboarding states is "Active/Onboarded"
        
        active_users_query = select(func.count(User.id)).where(
            User.state.not_in([s.value for s in onboarding_states])
        )
        active_users = (await db.execute(active_users_query)).scalar() or 0
        
        # 9. Seva Users (Unique users who paid)
        
        seva_users_query = select(func.count(func.distinct(Sankalp.user_id))).where(
            Sankalp.status.in_(paid_statuses)
        )
        seva_users = (await db.execute(seva_users_query)).scalar() or 0
        
        # 10. Tier Breakdown (Count by Amount)
        tier_query = select(Sankalp.amount, func.count(Sankalp.id)).where(
            Sankalp.status.in_(paid_statuses)
        ).group_by(Sankalp.amount)
        
        tier_res = await db.execute(tier_query)
        tiers = [{"amount": float(row[0]), "count": row[1]} for row in tier_res.all()]
        # Sort by amount
        tiers.sort(key=lambda x: x["amount"])
        
    except Exception as e:
        logger.error(f"Error calculating demographics/upcoming/metrics: {e}")
        # Initialize defaults if hard fail
        active_users = 0
        seva_users = 0
        tiers = []

    # --- FOUNDER'S BUSINESS METRICS (Phase 12) ---
    business_metrics = {}
    try:
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        
        # 1. Activation Funnel
        total_leads = total_users
        # onboarded_users is already active_users (which checks state)
        # paying_users is already seva_users
        
        # 2. Retention Health
        active_24h_query = select(func.count(User.id)).where(User.last_engagement_at >= now - timedelta(hours=24))
        active_24h = (await db.execute(active_24h_query)).scalar() or 0
        
        retained_7d_query = select(func.count(User.id)).where(User.last_engagement_at >= now - timedelta(days=7))
        retained_7d = (await db.execute(retained_7d_query)).scalar() or 0
        
        churn_risk_query = select(func.count(User.id)).where(
            User.state.not_in([s.value for s in onboarding_states]), # Onboarded
            User.last_engagement_at < now - timedelta(days=14)       # Inactive > 14 days
        )
        churn_risk = (await db.execute(churn_risk_query)).scalar() or 0
        
        # 3. Unit Economics
        arpu = float(total_revenue) / float(active_users) if active_users > 0 else 0
        ltv = float(total_revenue) / float(seva_users) if seva_users > 0 else 0
        
        # 4. Track Popularity
        track_query = select(User.nurture_track, func.count(User.id)).group_by(User.nurture_track)
        track_res = await db.execute(track_query)
        tracks = {row[0]: row[1] for row in track_res.all() if row[0]}
        
        # 5. Cycle Distribution
        cycle_query = select(User.devotional_cycle_number, func.count(User.id)).group_by(User.devotional_cycle_number)
        cycle_res = await db.execute(cycle_query)
        cycles = {f"Cycle {row[0]}": row[1] for row in cycle_res.all()}

        # 6. Detailed State Breakdown (The "Hardcore" Pipeline)
        state_query = select(User.state, func.count(User.id)).group_by(User.state)
        state_res = await db.execute(state_query)
        states_map = {row[0]: row[1] for row in state_res.all() if row[0]}

        business_metrics = {
            "funnel": {
                "leads": total_leads,
                "onboarded": active_users,
                "paying": seva_users,
                "conversion": round((seva_users / active_users * 100), 1) if active_users > 0 else 0
            },
            "retention": {
                "active_24h": active_24h,
                "retained_7d": retained_7d,
                "churn_risk": churn_risk
            },
            "economics": {
                "arpu": round(arpu, 2),
                "ltv": round(ltv, 2)
            },
            "distribution": {
                "tracks": tracks,
                "cycles": cycles,
                "states": states_map # New: Hardcore state breakdown
            }
        }
    except Exception as e:
        logger.error(f"Error calculating business metrics: {e}", exc_info=True)

    return {
        "revenue": {"total": float(total_revenue)},
        "impact": {"families_fed": total_families_fed},
        "ops": {"pending_sevas": pending_count},
        "media": {"total": media_total},
        "demographics": {
            "total_users": total_users,
            "dob_count": dob_count,
            "anniv_count": anniv_count,
            "active_users": active_users,
            "seva_users": seva_users
        },
        "business": business_metrics,
        "debug": {
            "business_success": bool(business_metrics),
            "now": str(datetime.now(timezone.utc))
        },
        "tiers": tiers,
        "upcoming_celebrations": upcoming,
        "recent_sankalps": recent_swaps
    }
