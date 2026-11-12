@echo off
chcp 65001 >nul
cd /d "%~dp0"
title JelE Clipper (safe mode)
if exist python\python.exe (python\python.exe clipper.py --veilig) else (.venv\Scripts\python clipper.py --veilig)
pause
