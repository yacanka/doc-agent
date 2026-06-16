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

cd /d "%PROJECT_ROOT%" || exit /b 1

if not exist "%REQUIREMENTS_FILE%" (
    echo ERROR: requirements.txt was not found in %PROJECT_ROOT%.
    exit /b 1
)

call :ensure_directory "%WHEELS_DIR%" || exit /b 1
call :ensure_directory "%MODELS_DIR%" || exit /b 1
call :ensure_directory "%WORKSPACE_DIR%" || exit /b 1

call :find_python || exit /b 1
echo Using Python command: %PYTHON_CMD%

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo Creating project-local virtual environment...
    %PYTHON_CMD% -m venv "%VENV_DIR%" || exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat" || exit /b 1
set "PIP_CACHE_DIR=%WORKSPACE_DIR%\pip-cache"
set "PYTHONPYCACHEPREFIX=%WORKSPACE_DIR%\pycache"

python -m pip install --upgrade pip || exit /b 1
echo Downloading dependency wheels into %WHEELS_DIR%...
python -m pip download --dest "%WHEELS_DIR%" --requirement "%REQUIREMENTS_FILE%" || exit /b 1

echo Installing dependencies from local wheels only...
python -m pip install --no-index --find-links "%WHEELS_DIR%" --requirement "%REQUIREMENTS_FILE%" || exit /b 1

call :resolve_model_path || exit /b 1
call :prepare_model || exit /b 1
call :write_status || exit /b 1

echo Setup completed successfully. Status written to %STATUS_FILE%.
exit /b 0

:ensure_directory
if not exist "%~1" mkdir "%~1"
exit /b %ERRORLEVEL%

:find_python
py -3 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    exit /b 0
)
python --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    exit /b 0
)
echo ERROR: Python 3 was not found. Install Python 3 and re-run this script.
exit /b 1

:resolve_model_path
for /f "usebackq delims=" %%I in (`python -c "import json, pathlib; p=pathlib.Path('config.json'); d=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}; print(d.get('model_path','models/model.gguf'))"`) do set "CONFIGURED_MODEL_PATH=%%I"
python -c "import pathlib, sys; p=pathlib.Path(sys.argv[1]); print((p if p.is_absolute() else pathlib.Path.cwd()/p).resolve())" "%CONFIGURED_MODEL_PATH%" > "%WORKSPACE_DIR%\model_path.tmp" || exit /b 1
set /p "MODEL_PATH=" < "%WORKSPACE_DIR%\model_path.tmp"
del "%WORKSPACE_DIR%\model_path.tmp" >nul 2>nul
exit /b 0

:prepare_model
if exist "%MODEL_PATH%" (
    echo Found configured GGUF model: %MODEL_PATH%
    exit /b 0
)
if defined MODEL_URL (
    call :download_model_from_url || exit /b 1
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
exit /b 1

:download_model_from_url
echo Downloading GGUF model from MODEL_URL into %MODEL_PATH%...
python -c "import os, pathlib, sys, urllib.request; url=os.environ['MODEL_URL']; target=pathlib.Path(sys.argv[1]); assert url.lower().startswith('https://'), 'MODEL_URL must use HTTPS'; target.parent.mkdir(parents=True, exist_ok=True); urllib.request.urlretrieve(url, target)" "%MODEL_PATH%"
exit /b %ERRORLEVEL%

:write_status
python -c "import json, pathlib, sys, time; workspace=pathlib.Path('workspace'); data={'status':'complete','completed_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),'venv':'.venv','wheels':'wheels','model_path':sys.argv[1]}; workspace.mkdir(exist_ok=True); (workspace/'setup_complete.json').write_text(json.dumps(data, indent=2), encoding='utf-8')" "%CONFIGURED_MODEL_PATH%"
exit /b %ERRORLEVEL%
