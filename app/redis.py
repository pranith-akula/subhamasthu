"""
Redis client configuration using redis-py (asyncio).
"""

from typing import Optional
import logging

from redis import asyncio as aioredis
from redis.asyncio.client import Redis

from app.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client wrapper."""
    
    _client: Optional[Redis] = None
    
    @classmethod
    def get_client(cls) -> Redis:
        """Get or create Redis client."""
        if cls._client is None:
            if not settings.redis_url:
                logger.warning("REDIS_URL not set. Using mock/disabled client.")
                # We could return a mock here, or raise. For now, let's just log.
                # In prod, we want to crash if Redis is missing.
                pass
            
            # Create client connection pool
            cls._client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=5.0,
                health_check_interval=30
            )
            logger.info("Redis client initialized")
            
        return cls._client

    @classmethod
    async def close(cls):
        """Close Redis client."""
        if cls._client:
            await cls._client.close()
            cls._client = None
            logger.info("Redis client closed")


# Convenience function to get redis
async def get_redis() -> Redis:
    """ Dependency for getting redis connection."""
    return RedisClient.get_client()
