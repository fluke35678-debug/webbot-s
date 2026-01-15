@echo off
title Godwin Control Center - Production

echo [SYSTEM] Starting Godwin Control Center...
echo [SYSTEM] Loading environment variables...

:: Check if venv exists, if so activate it
if exist "venv\Scripts\activate.bat" (
    echo [SYSTEM] Activating Virtual Environment...
    call venv\Scripts\activate.bat
)

:: Install requirements if needed (uncomment to enable auto-install)
:: echo [SYSTEM] Checking dependencies...
:: pip install -r requirements.txt

echo.
echo [1/2] Starting Discord Bot...
start "Godwin Bot" /min cmd /k "python bot/main.py"

echo [2/2] Starting Web Dashboard (FastAPI)...
echo [INFO] Dashboard will be available at: http://localhost:8000
echo [INFO] To access from other devices, use your local IP:8000
echo.

:: Run Uvicorn with 0.0.0.0 to allow external access
python -m uvicorn main_dashboard:app --host 0.0.0.0 --port 8000 --reload

pause
