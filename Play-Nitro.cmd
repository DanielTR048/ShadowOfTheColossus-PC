@echo off
cd /d "%~dp0"
"%~dp0out\venv\Scripts\python.exe" "%~dp0tools\run_nitro.py"
if errorlevel 1 pause
