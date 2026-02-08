"""
Celery application configuration.
"""

from celery import Celery
from celery.schedules import crontab

from app.config import settings

# Create Celery app
celery_app = Celery(
    "subhamasthu",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.daily_rashiphalalu",
        "app.workers.weekly_sankalp",
        "app.workers.hourly_nurture",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # Hourly Nurture Check (Handles Rashi & Nurture)
    "hourly-nurture-check": {
        "task": "app.workers.hourly_nurture.process_hourly_nurture",
        "schedule": crontab(minute=0, hour="*"),
    },
    # DEPRECATED: Daily Rashiphalalu at 7:00 AM CST (Replaced by Hourly)
    # "daily-rashiphalalu-broadcast": {
    #     "task": "app.workers.daily_rashiphalalu.broadcast_daily_rashiphalalu",
    #     "schedule": crontab(hour=7, minute=0),
    # },
    # Check for weekly sankalp prompts daily at 7:30 AM CST
    "weekly-sankalp-check": {
        "task": "app.workers.weekly_sankalp.send_weekly_sankalp_prompts",
        "schedule": crontab(hour=7, minute=30),
    },
}
