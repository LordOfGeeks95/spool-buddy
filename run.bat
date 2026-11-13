@echo off
REM Double-click to start Spool Buddy from source.
REM The first time it creates .venv and installs the packages (needs internet).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo First run: setting things up...
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
".venv\Scripts\python.exe" main.py
pause
