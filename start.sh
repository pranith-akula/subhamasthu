#!/bin/bash
# Startup script for Railway deployment
# Ensures PORT environment variable is properly handled

PORT=${PORT:-8000}
echo "Starting Subhamasthu API on port $PORT"
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
