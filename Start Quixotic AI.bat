@echo off
rem Double-click to start Quixotic AI on this PC and open it in your browser.
cd /d "%~dp0"
echo Starting the database...
rem Docker PostgreSQL + pgvector (docker-compose.yml). Docker Desktop must be running.
docker compose up -d postgres || (echo Docker is not running - start Docker Desktop and try again. & pause & exit /b 1)
timeout /t 5 /nobreak >nul
echo Starting Quixotic AI (keep this window open; close it to stop)...
start "" /min cmd /c "timeout /t 20 /nobreak >nul & start http://localhost:8000"
if exist ".venv\Scripts\python.exe" (".venv\Scripts\python.exe" scripts\dev_up.py) else (python scripts\dev_up.py)
pause
