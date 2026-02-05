"""
Database connection and session management for Neon Postgres.
Uses asyncpg with SQLAlchemy async.
"""

import ssl
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def get_database_url() -> str:
    """Get database URL without sslmode and with proper params."""
    url = settings.database_url
    if not url:
        return ""
    # Remove sslmode from URL (asyncpg doesn't support it as query param)
    if "?sslmode=" in url:
        url = url.split("?sslmode=")[0]
    elif "&sslmode=" in url:
        url = url.replace("&sslmode=require", "").replace("&sslmode=disable", "")
    return url


def create_engine_if_configured() -> Optional[AsyncEngine]:
    """Create async engine only if DATABASE_URL is configured."""
    db_url = get_database_url()
    if not db_url:
        print("WARNING: DATABASE_URL not configured. Database features disabled.")
        return None
    
    return create_async_engine(
        db_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={"ssl": True},  # Enable SSL for Neon
    )


# Create async engine for Neon Postgres with SSL (may be None if not configured)
engine = create_engine_if_configured()

# Session factory (only if engine exists)
async_session_maker = (
    async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    if engine
    else None
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    if not async_session_maker:
        raise RuntimeError("Database not configured. Set DATABASE_URL environment variable.")
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for database session (for use outside FastAPI)."""
    if not async_session_maker:
        raise RuntimeError("Database not configured. Set DATABASE_URL environment variable.")
    
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    if not engine:
        print("Skipping database initialization - DATABASE_URL not configured")
        return
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    if engine:
        await engine.dispose()
