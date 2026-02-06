@echo off
echo Starting Seva Footage Watcher in background...
start pythonw scripts/watch_footage.py
echo.
echo ✅ Watcher is now running hidden in the background!
echo You can close this terminal now.
echo.
echo To stop it later, use Task Manager or run stop_watcher.bat
pause
