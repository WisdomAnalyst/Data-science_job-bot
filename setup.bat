@echo off
echo ============================================================
echo  DS Job Bot - First-Time Setup
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

echo [1/2] Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. Try running as Administrator.
    pause
    exit /b 1
)

echo.
echo [2/2] Setup complete!
echo.
echo NEXT STEPS:
echo   1. Open config.json and add your free API keys for more sources.
echo   2. Run start.bat to launch the dashboard.
echo   3. Visit http://localhost:5000 in your browser.
echo.
echo FREE API KEYS (optional but recommended):
echo   Adzuna   : https://developer.adzuna.com
echo   JSearch  : https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
echo   Reed UK  : https://www.reed.co.uk/developers/jobseeker
echo.
pause
