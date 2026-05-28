@echo off
echo ============================================================
echo  DS Job Bot — Starting Dashboard
echo ============================================================
echo.
echo  Dashboard: http://localhost:5000
echo  Auto-fetches daily at 06:00 UTC
echo  Press Ctrl+C to stop
echo.
cd /d "%~dp0"
python app.py
pause
