@echo off
echo ===================================================
echo   Subhamasthu Automation Starter
echo   Starting Web Server, Worker, and Scheduler...
echo ===================================================

:: 1. Start Web Server in a new window
echo Starting Web Server...
start "Subhamasthu Web" cmd /k "python run.py"

:: 2. Start Celery Worker in a new window
echo Starting Celery Worker...
start "Subhamasthu Worker" cmd /k "celery -A app.workers.celery_app worker --loglevel=info --pool=solo"

:: 3. Start Celery Beat (Scheduler) in a new window
echo Starting Scheduler (Beat)...
start "Subhamasthu Scheduler" cmd /k "celery -A app.workers.celery_app beat --loglevel=info"

echo ===================================================
echo   All systems started!
echo   DO NOT CLOSE the popup windows.
echo   You can minimize them.
echo ===================================================
pause
