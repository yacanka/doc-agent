@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "PROJECT_ROOT=%~dp0"
set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"
set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "WHEELS_DIR=%PROJECT_ROOT%\wheels"
set "MODELS_DIR=%PROJECT_ROOT%\models"
set "WORKSPACE_DIR=%PROJECT_ROOT%\workspace"
set "STATUS_FILE=%WORKSPACE_DIR%\setup_complete.json"
set "MODEL_HINT_FILE=%MODELS_DIR%\MODEL_PLACEMENT.txt"
set "REQUIREMENTS_FILE=%PROJECT_ROOT%\requirements.txt"

cd /d "%PROJECT_ROOT%" || goto handle_error

if not exist "%REQUIREMENTS_FILE%" (
    echo ERROR: requirements.txt was not found in %PROJECT_ROOT%.
    goto handle_error
)

call :ensure_directory "%WHEELS_DIR%" || goto handle_error
call :ensure_directory "%MODELS_DIR%" || goto handle_error
call :ensure_directory "%WORKSPACE_DIR%" || goto handle_error

call :find_python || goto handle_error
echo Using Python command: %PYTHON_CMD%
call :check_python_version "%PYTHON_CMD%" || goto handle_error

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating project-local virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%" || goto handle_error
)

call "%VENV_DIR%\Scripts\activate.bat" || goto handle_error
call :check_python_version "python" || goto handle_error
set "PIP_CACHE_DIR=%WORKSPACE_DIR%\pip-cache"
set "PYTHONPYCACHEPREFIX=%WORKSPACE_DIR%\pycache"

python -m pip install --upgrade pip || goto handle_error
echo Removing stale model backend source archives from %WHEELS_DIR%...
del /q "%WHEELS_DIR%\gpt4all-*.tar.gz" >nul 2>nul

echo Downloading dependency wheels into %WHEELS_DIR%...
python -m pip download --only-binary=:all: --prefer-binary --dest "%WHEELS_DIR%" --requirement "%REQUIREMENTS_FILE%" || goto handle_error
call :ensure_gpt4all_wheel || goto handle_error

echo Installing dependencies from local wheels only...
python -m pip install --no-index --find-links "%WHEELS_DIR%" --requirement "%REQUIREMENTS_FILE%" || goto handle_error

call :resolve_model_path || goto handle_error
call :prepare_model || goto handle_error
call :write_status || goto handle_error

echo Setup completed successfully. Status written to %STATUS_FILE%.
pause>nul
exit /b 0

:ensure_directory
if not exist "%~1" mkdir "%~1"
exit /b %ERRORLEVEL%

:find_python
py -3.12 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.12"
    exit /b 0
)
py -3.11 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.11"
    exit /b 0
)
py -3.10 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.10"
    exit /b 0
)
python --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    exit /b 0
)
echo ERROR: Python 3.10, 3.11, or 3.12 was not found. Install Python 3.12 and re-run this script.
goto handle_error

:check_python_version
for /f "usebackq delims=" %%I in (`%~1 -c "import sys; version=sys.version_info; print(f'{version.major}.{version.minor}.{version.micro}'); raise SystemExit(0 if version.major == 3 and 10 <= version.minor <= 12 else 1)"`) do set "PYTHON_VERSION=%%I"
if errorlevel 1 (
    echo ERROR: Unsupported Python version: %PYTHON_VERSION%
    echo This project currently supports Python 3.10, 3.11, or 3.12 on Windows.
    echo Python 3.13+ and 3.14 can force source builds for native packages.
    echo Install Python 3.12 from python.org, delete .venv, and re-run setup_online.bat.
    goto handle_error
)
echo Detected supported Python version: %PYTHON_VERSION%
exit /b 0

:ensure_gpt4all_wheel
if exist "%WHEELS_DIR%\gpt4all-*.whl" exit /b 0
echo ERROR: A prebuilt gpt4all wheel was not downloaded.
echo Source builds require native compiler tooling and are intentionally blocked for offline setup.
echo Confirm Python is 3.10, 3.11, or 3.12 on 64-bit Windows, then re-run setup_online.bat.
goto handle_error

:resolve_model_path
for /f "usebackq delims=" %%I in (`python -c "import json, pathlib; p=pathlib.Path('config.json'); d=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}; print(d.get('model_path','models/model.gguf'))"`) do set "CONFIGURED_MODEL_PATH=%%I"
python -c "import pathlib, sys; p=pathlib.Path(sys.argv[1]); print((p if p.is_absolute() else pathlib.Path.cwd()/p).resolve())" "%CONFIGURED_MODEL_PATH%" > "%WORKSPACE_DIR%\model_path.tmp" || goto handle_error
set /p "MODEL_PATH=" < "%WORKSPACE_DIR%\model_path.tmp"
del "%WORKSPACE_DIR%\model_path.tmp" >nul 2>nul
exit /b 0

:prepare_model
if exist "%MODEL_PATH%" (
    echo Found configured GGUF model: %MODEL_PATH%
    exit /b 0
)
if defined MODEL_URL (
    call :download_model_from_url || goto handle_error
    exit /b 0
)
(
    echo The configured GGUF model was not found.
    echo.
    echo Place the model at:
    echo %MODEL_PATH%
    echo.
    echo Alternatively, set MODEL_URL to a trusted HTTPS GGUF download URL and re-run setup_online.bat.
    echo Example:
    echo set MODEL_URL=https://example.invalid/path/to/model.gguf
    echo setup_online.bat
) > "%MODEL_HINT_FILE%"
echo ERROR: GGUF model is missing. See %MODEL_HINT_FILE%.
echo No setup completion marker was written.
goto handle_error

:download_model_from_url
echo Downloading GGUF model from MODEL_URL into %MODEL_PATH%...
python -c "import os, pathlib, sys, urllib.request; url=os.environ['MODEL_URL']; target=pathlib.Path(sys.argv[1]); assert url.lower().startswith('https://'), 'MODEL_URL must use HTTPS'; target.parent.mkdir(parents=True, exist_ok=True); urllib.request.urlretrieve(url, target)" "%MODEL_PATH%"
exit /b %ERRORLEVEL%

:write_status
python -c "import json, pathlib, sys, time; workspace=pathlib.Path('workspace'); data={'status':'complete','completed_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),'venv':'.venv','wheels':'wheels','model_path':sys.argv[1]}; workspace.mkdir(exist_ok=True); (workspace/'setup_complete.json').write_text(json.dumps(data, indent=2), encoding='utf-8')" "%CONFIGURED_MODEL_PATH%"
exit /b %ERRORLEVEL%

:handle_error
pause
exit /b 1