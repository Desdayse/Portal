@echo off
setlocal
cd /d "%~dp0"
if exist "dist\updated\Portal\Portal.exe" (
    start "" "dist\updated\Portal\Portal.exe"
    exit /b 0
)
if exist "dist\Portal\Portal.exe" (
    start "" "dist\Portal\Portal.exe"
    exit /b 0
)
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto error
)
".venv\Scripts\python.exe" -c "import PySide6" >nul 2>&1
if errorlevel 1 (
    python -m pip --python ".venv\Scripts\python.exe" install -r requirements.txt
    if errorlevel 1 goto error
)
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto error
exit /b 0
:error
echo Portal could not start. Check Python 3.11+ and internet for first setup.
echo See README.md for help. Files have not been changed by this launcher.
pause
exit /b 1
