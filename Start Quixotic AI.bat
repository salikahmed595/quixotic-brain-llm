@echo off
rem Double-click to start Quixotic AI on this PC and open it in your browser.
cd /d "%~dp0"
echo Starting the database...
docker compose up -d postgres
echo Starting Quixotic AI (keep this window open; close it to stop)...
start "" /min cmd /c "timeout /t 20 /nobreak >nul & start http://localhost:8000"
python scripts\dev_up.py
pause
