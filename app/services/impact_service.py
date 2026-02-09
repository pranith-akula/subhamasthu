"""
Impact Service - Aggregates impact metrics from verified seva executions.

All public metrics are derived from verified seva_execution records only.
This ensures: What happened IRL = What shows on dashboard.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.seva_execution import SevaExecution, SevaExecutionStatus
from app.models.sankalp import Sankalp
from app.models.temple import Temple
from app.models.user import User

logger = logging.getLogger(__name__)

# Redis cache TTL (5 minutes)
CACHE_TTL_SECONDS = 300


class ImpactService:
    """
    Service for aggregating impact metrics.
    
    Key principle: Only verified executions count toward public impact.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_global_impact(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get global impact metrics (public endpoint).
        
        Returns:
            Dictionary with total_meals, this_month_meals, this_week_meals,
            active_devotees, cities, last_seva_date.
        
        Note: Only verified executions are counted.
        """
        # Try Redis cache first
        if use_cache:
            cached = await self._get_cached_impact()
            if cached:
                return cached
        
        ist = ZoneInfo("Asia/Kolkata")
        now = datetime.now(ist)
        
        # Calculate time boundaries
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Verified status filter
        verified_status = SevaExecutionStatus.VERIFIED.value
        
        # Total meals (all time, verified only)
        total_result = await self.db.execute(
            select(func.coalesce(func.sum(SevaExecution.meals_served), 0))
            .where(SevaExecution.status == verified_status)
        )
        total_meals = total_result.scalar() or 0
        
        # This month meals
        month_result = await self.db.execute(
            select(func.coalesce(func.sum(SevaExecution.meals_served), 0))
            .where(SevaExecution.status == verified_status)
            .where(SevaExecution.verified_at >= month_start)
        )
        this_month_meals = month_result.scalar() or 0
        
        # This week meals
        week_result = await self.db.execute(
            select(func.coalesce(func.sum(SevaExecution.meals_served), 0))
            .where(SevaExecution.status == verified_status)
            .where(SevaExecution.verified_at >= week_start)
        )
        this_week_meals = week_result.scalar() or 0
        
        # Active devotees (unique donors this month)
        devotees_result = await self.db.execute(
            select(func.count(distinct(Sankalp.user_id)))
            .select_from(SevaExecution)
            .join(Sankalp, SevaExecution.sankalp_id == Sankalp.id)
            .where(SevaExecution.status == verified_status)
            .where(SevaExecution.verified_at >= month_start)
        )
        active_devotees = devotees_result.scalar() or 0
        
        # Cities (from temples)
        cities_result = await self.db.execute(
            select(distinct(Temple.city))
            .select_from(SevaExecution)
            .join(Temple, SevaExecution.temple_id == Temple.id)
            .where(SevaExecution.status == verified_status)
            .where(Temple.city.isnot(None))
        )
        cities = [row[0] for row in cities_result.fetchall() if row[0]]
        
        # Last seva date
        last_seva_result = await self.db.execute(
            select(SevaExecution.verified_at)
            .where(SevaExecution.status == verified_status)
            .order_by(SevaExecution.verified_at.desc())
            .limit(1)
        )
        last_seva_row = last_seva_result.first()
        last_seva_date = last_seva_row[0].strftime("%Y-%m-%d") if last_seva_row and last_seva_row[0] else None
        
        impact_data = {
            "total_meals": int(total_meals),
            "this_month_meals": int(this_month_meals),
            "this_week_meals": int(this_week_meals),
            "active_devotees": int(active_devotees),
            "cities": cities,
            "last_seva_date": last_seva_date,
        }
        
        # Cache the result
        await self._cache_impact(impact_data)
        
        return impact_data
    
    async def get_user_impact(self, user_id) -> Dict[str, Any]:
        """
        Get personal impact for a specific user.
        
        Returns:
            Dictionary with lifetime_meals and sankalp_count.
        """
        verified_status = SevaExecutionStatus.VERIFIED.value
        
        # Lifetime meals from verified executions
        meals_result = await self.db.execute(
            select(func.coalesce(func.sum(SevaExecution.meals_served), 0))
            .select_from(SevaExecution)
            .join(Sankalp, SevaExecution.sankalp_id == Sankalp.id)
            .where(Sankalp.user_id == user_id)
            .where(SevaExecution.status == verified_status)
        )
        lifetime_meals = meals_result.scalar() or 0
        
        # Sankalp count (verified)
        count_result = await self.db.execute(
            select(func.count(SevaExecution.id))
            .select_from(SevaExecution)
            .join(Sankalp, SevaExecution.sankalp_id == Sankalp.id)
            .where(Sankalp.user_id == user_id)
            .where(SevaExecution.status == verified_status)
        )
        sankalp_count = count_result.scalar() or 0
        
        return {
            "lifetime_meals": int(lifetime_meals),
            "sankalp_count": int(sankalp_count),
        }
    
    async def get_weekly_summary_data(self) -> Dict[str, Any]:
        """
        Get data for weekly summary message.
        
        Returns:
            Dictionary with devotees, meals, cities for this week.
        """
        ist = ZoneInfo("Asia/Kolkata")
        now = datetime.now(ist)
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        verified_status = SevaExecutionStatus.VERIFIED.value
        
        # This week devotees
        devotees_result = await self.db.execute(
            select(func.count(distinct(Sankalp.user_id)))
            .select_from(SevaExecution)
            .join(Sankalp, SevaExecution.sankalp_id == Sankalp.id)
            .where(SevaExecution.status == verified_status)
            .where(SevaExecution.verified_at >= week_start)
        )
        devotees = devotees_result.scalar() or 0
        
        # This week meals
        meals_result = await self.db.execute(
            select(func.coalesce(func.sum(SevaExecution.meals_served), 0))
            .where(SevaExecution.status == verified_status)
            .where(SevaExecution.verified_at >= week_start)
        )
        meals = meals_result.scalar() or 0
        
        # This week cities
        cities_result = await self.db.execute(
            select(func.count(distinct(Temple.city)))
            .select_from(SevaExecution)
            .join(Temple, SevaExecution.temple_id == Temple.id)
            .where(SevaExecution.status == verified_status)
            .where(SevaExecution.verified_at >= week_start)
            .where(Temple.city.isnot(None))
        )
        cities = cities_result.scalar() or 0
        
        return {
            "devotees": int(devotees),
            "meals": int(meals),
            "cities": int(cities),
        }
    
    async def _get_cached_impact(self) -> Optional[Dict[str, Any]]:
        """Get cached impact from Redis."""
        try:
            from app.redis import get_redis
            import json
            
            redis = await get_redis()
            cached = await redis.get("subhamasthu:impact:global")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis cache miss: {e}")
        return None
    
    async def _cache_impact(self, data: Dict[str, Any]) -> None:
        """Cache impact data to Redis."""
        try:
            from app.redis import get_redis
            import json
            
            redis = await get_redis()
            await redis.setex(
                "subhamasthu:impact:global",
                CACHE_TTL_SECONDS,
                json.dumps(data)
            )
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")
