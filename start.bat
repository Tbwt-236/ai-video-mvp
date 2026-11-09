@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  python bootstrap.py
) else (
  py -3 bootstrap.py
)
if errorlevel 1 pause
