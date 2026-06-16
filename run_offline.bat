@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "PROJECT_ROOT=%~dp0"
set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "WORKSPACE_DIR=%PROJECT_ROOT%\workspace"
set "STATUS_FILE=%WORKSPACE_DIR%\setup_complete.json"

cd /d "%PROJECT_ROOT%" || exit /b 1

if not exist "%STATUS_FILE%" (
    echo ERROR: Offline setup has not completed.
    echo Run setup_online.bat on a connected machine first.
    exit /b 1
)

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo ERROR: Local virtual environment was not found at %VENV_DIR%.
    echo Re-run setup_online.bat to recreate it.
    exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat" || exit /b 1
call :configure_offline_runtime
call :resolve_server || exit /b 1

echo Starting Offline Document Agent at %LOCAL_URL%
start "" "%LOCAL_URL%"
python -m uvicorn app.main:app --host "%APP_HOST%" --port "%APP_PORT%"
exit /b %ERRORLEVEL%

:configure_offline_runtime
set "PIP_NO_INDEX=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_FIND_LINKS=%PROJECT_ROOT%\wheels"
set "PIP_CACHE_DIR=%WORKSPACE_DIR%\pip-cache"
set "PYTHONPYCACHEPREFIX=%WORKSPACE_DIR%\pycache"
set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"
set "NO_PROXY=*"
set "UVICORN_NO_ACCESS_LOG=0"
exit /b 0

:resolve_server
for /f "usebackq tokens=1,2" %%A in (`python -c "from app.config import load_config; c=load_config(); print(c.host, c.port)"`) do (
    set "APP_HOST=%%A"
    set "APP_PORT=%%B"
)
if not defined APP_HOST set "APP_HOST=127.0.0.1"
if not defined APP_PORT set "APP_PORT=8000"
set "LOCAL_URL=http://%APP_HOST%:%APP_PORT%/docs"
exit /b 0
