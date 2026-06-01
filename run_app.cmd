@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch_app.ps1"
if errorlevel 1 (
    echo.
    echo Failed to launch Runet Niche Analyzer. Check out\logs for details.
    pause
)
