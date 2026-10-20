@echo off
rem Shark Support installer launcher (Windows) - WORK IN PROGRESS
rem Copyright Matthew Armstrong. PolyForm Noncommercial 1.0.0. No warranty.
cd /d "%~dp0"
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY (where python >nul 2>nul && set PY=python)
if not defined PY (
  echo Shark Support needs Python 3.8 or newer: https://www.python.org/downloads/
  echo Tick "Add python.exe to PATH" while installing, then double-click this file again.
  pause
  exit /b 1
)
%PY% -c "import tkinter" >nul 2>nul
if errorlevel 1 (
  echo The installer window needs tkinter. Running the text installer instead...
  %PY% install.py --cli
  pause
  exit /b 0
)
%PY% install.py
if errorlevel 1 pause
