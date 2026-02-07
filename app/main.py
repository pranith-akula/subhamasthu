"""
FastAPI application entry point.
Configures routes, middleware, and lifecycle events.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db, close_db
from app.logging_config import configure_logging
from app.logging_config import configure_logging
from app.redis import RedisClient
import logging

# Import routers - MUST BE AT TOP LEVEL
from app.api.webhooks.gupshup import router as gupshup_router
from app.api.webhooks.razorpay import router as razorpay_router
from app.api.admin.broadcast import router as broadcast_router
from app.api.admin.seva import router as seva_router
from app.api.admin.seva_media import router as seva_media_router
from app.api.admin.database import router as database_router

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle manager."""
    # Startup
    configure_logging()
    logging.info("Starting up Subhamasthu...")
    
    # Initialize Redis
    try:
        RedisClient.get_client()
    except Exception as e:
        logging.warning(f"Failed to initialize Redis: {e}")

    yield
    
    # Shutdown
    await RedisClient.close()
    await close_db()
    logging.info("Shutting down...")


app = FastAPI(
    title="Subhamasthu",
    description="Telugu NRI Dharmic Sankalp Platform",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.debug,
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal Server Error"},
    )

# CORS middleware
# CORS middleware
origins = [
    "https://pranith-akula.github.io",
    "https://web-production-b998a.up.railway.app",
]
if settings.is_development:
    origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
app.include_router(
    seva_media_router,
    prefix="/admin",
    tags=["admin"],
)
app.include_router(
    database_router,
    prefix="/admin",
    tags=["admin"],
)

# Admin Dashboard (HTML)
from app.api.admin.dashboard import router as dashboard_router
app.include_router(dashboard_router)

# Serve Static Files (Main Website)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Mount static files
app.mount("/static", StaticFiles(directory="docs"), name="static")

@app.get("/")
async def read_root():
    return FileResponse("docs/index.html")
