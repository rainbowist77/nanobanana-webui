@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" app.py %*
if errorlevel 1 goto failed
exit /b 0
:failed
echo Application failed to start. Check the error above.
pause
exit /b 1
