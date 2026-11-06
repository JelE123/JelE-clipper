@echo off
goto main
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit              
exit
exit     
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
exit
:main
rem The lines above catch an old start.bat window: when an update replaces this
rem file while it runs, Windows keeps reading it at the old spot. It lands on
rem "exit" and closes, instead of running half a line. Everything below sits in
rem one block, so Windows reads it at once and never reads this file again.
(
chcp 65001 >nul
cd /d "%~dp0"
title JelE Clipper
if not exist .venv (
  echo Run install.bat first.
  pause
  exit /b
)
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt
.venv\Scripts\python clipper.py %*
if errorlevel 1 if exist data\update_pending.json (
  echo.
  echo  The new version does not start properly. Putting the previous version back...
  .venv\Scripts\python herstel.py
  .venv\Scripts\python clipper.py %*
)
if "%~1"=="" pause
exit /b
)
