@echo off
cd /d "%~dp0"
if exist ".venv-studio\Scripts\python.exe" (
  ".venv-studio\Scripts\python.exe" studio.py
) else (
  python studio.py
)
if errorlevel 1 pause
