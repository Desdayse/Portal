@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto error
python -m pip --python ".venv\Scripts\python.exe" install -r requirements.txt pyinstaller
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m unittest discover -s tests
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm --distpath dist/updated Portal.spec
if errorlevel 1 goto error
".venv\Scripts\python.exe" tests\smoke_exe.py dist\updated\Portal\Portal.exe
if errorlevel 1 goto error
echo Ready: dist\updated\Portal\Portal.exe. Keep the whole Portal folder together.
pause
exit /b 0
:error
echo Build failed. See the error above.
pause
exit /b 1
