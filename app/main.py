"""
FastAPI application entry point.
Configures routes, middleware, and lifecycle events.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db, close_db

# Import routers
from app.api.webhooks.gupshup import router as gupshup_router
from app.api.webhooks.razorpay import router as razorpay_router
from app.api.admin.broadcast import router as broadcast_router
from app.api.admin.seva import router as seva_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle manager."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="Subhamasthu",
    description="Telugu NRI Dharmic Sankalp Platform",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.debug,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "env": settings.app_env,
    }


# Register webhook routes
app.include_router(
    gupshup_router,
    prefix="/webhooks",
    tags=["webhooks"],
)
app.include_router(
    razorpay_router,
    prefix="/webhooks",
    tags=["webhooks"],
)

# Register admin routes
app.include_router(
    broadcast_router,
    prefix="/admin",
    tags=["admin"],
)
app.include_router(
    seva_router,
    prefix="/admin",
    tags=["admin"],
)
