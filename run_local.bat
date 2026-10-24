@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  set "PYTHON_CMD=python"
) else (
  set "PYTHON_CMD=py -3"
)

if not exist ".venv\Scripts\python.exe" (
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto :failed
)

rem Keep the pip cache and the temporary files on the project drive so that a full
rem system drive cannot break the dependency installation.
set "PIP_CACHE_DIR=%~dp0.pip-cache"
set "TMP=%~dp0.tmp"
set "TEMP=%~dp0.tmp"
if not exist "%TMP%" mkdir "%TMP%"

.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :failed
.venv\Scripts\python.exe scripts\setup_local_env.py
if errorlevel 1 goto :failed

rem Use local .env values only; do not inherit hosted credentials or a shared database URL.
set "APP_MODE="
set "LOCAL_AUTH_ENABLED="
set "LOCAL_ADMIN_USERNAME="
set "LOCAL_ADMIN_PASSWORD="
set "LOCAL_SESSION_SECRET="
set "DATABASE_URL="

echo Starting Lower Paung-Luang dashboard at http://127.0.0.1:3000
.venv\Scripts\python.exe -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 3000
if errorlevel 1 goto :failed
goto :eof

:failed
echo Local setup did not complete. Check that Python 3.12+ and internet access are available.
pause
exit /b 1
