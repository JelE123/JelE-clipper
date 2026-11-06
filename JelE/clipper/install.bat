@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Installing JelE Clipper
echo.
echo  Installing JelE Clipper. This takes a few minutes.
echo.
where py >nul 2>nul
if %errorlevel% neq 0 (
  echo  Python is not on your PC yet. Installing it now through winget...
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  echo.
  echo  Done. Close this window and double-click install.bat again.
  pause
  exit /b
)
if not exist .venv (
  py -3 -m venv .venv
)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
  echo.
  echo  Something went wrong while installing. Take a screenshot of this window.
  pause
  exit /b
)
echo.
echo  Done! From now on, start the clipper with start.bat
echo.
pause
