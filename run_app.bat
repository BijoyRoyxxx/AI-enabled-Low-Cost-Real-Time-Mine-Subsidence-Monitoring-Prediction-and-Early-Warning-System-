@echo off
title AI-Enabled Real Time Mine Subsidence Monitoring System
echo ===============================================================================
echo Starting AI-Enabled Low Cost Real Time Mine Subsidence Monitoring System...
echo Target: Bowen Basin Longwall Panel 4B - 4x5 LoRa Mesh & Extensometers
echo ===============================================================================

:: Check python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not added to PATH.
    pause
    exit /b 1
)

:: Install / verify dependencies if needed
echo [INFO] Verifying Python dependencies...
pip install -r backend\requirements.txt >nul 2>&1

:: Compile JSX if modified
if exist "frontend\App.jsx" (
    echo [INFO] Building frontend React scripts...
    call npx esbuild frontend\App.jsx --outfile=frontend\App.js >nul 2>&1
)

:: Open default browser after 2 seconds
start "" timeout /t 2 >nul & start http://localhost:8000/

:: Start FastAPI backend with Uvicorn
echo [INFO] Starting FastAPI Uvicorn Server on http://localhost:8000 ...
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
pause
