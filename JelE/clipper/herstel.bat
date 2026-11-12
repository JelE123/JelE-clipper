@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Restoring JelE Clipper
echo.
echo  Putting the previous version of JelE Clipper back.
echo.
if exist python\python.exe (python\python.exe herstel.py) else (.venv\Scripts\python herstel.py)
echo.
pause
