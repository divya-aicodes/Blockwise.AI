@echo off
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo .venv is missing. Create it with: py -m venv .venv ^&^& .\.venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0run_stage4.py"
pause
