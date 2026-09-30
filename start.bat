@echo off
rem Windows launcher: double-click. Builds if needed, starts Quant Pricer, opens the browser.
cd /d "%~dp0"
where uv >nul 2>nul || (echo uv is required: https://docs.astral.sh/uv/ & pause & exit /b 1)
where npm >nul 2>nul || (echo Node.js 20+ is required: https://nodejs.org/ & pause & exit /b 1)
uv run python scripts\launch.py %*
if errorlevel 1 pause
