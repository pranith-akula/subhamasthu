#!/bin/bash

# Start Celery Worker in background
celery -A app.workers.celery_app worker --loglevel=info &

# Start Celery Beat in background
celery -A app.workers.celery_app beat --loglevel=info &

# Start Web Server (Foreground)
python run.py
