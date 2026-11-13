@echo off
REM Double-click (or run in the terminal) to build "release\Spool Buddy.exe".
REM Details: tools\build_exe.py
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo No .venv found. Run run.bat once first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" tools\build_exe.py
pause
