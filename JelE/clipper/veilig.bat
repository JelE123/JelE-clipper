@echo off
chcp 65001 >nul
cd /d "%~dp0"
title JelE Clipper (safe mode)
.venv\Scripts\python clipper.py --veilig
pause
