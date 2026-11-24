@echo off
rem GRIN Reels - double-click to start (Windows). (c) 2026 Ernest Grin
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run install.ps1 first & pause & exit /b 1)
.venv\Scripts\python -m autocut.launch
pause
