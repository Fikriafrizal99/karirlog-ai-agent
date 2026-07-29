@echo off
setlocal
cd /d "%~dp0\..\.."
if not exist ".venv\Scripts\python.exe" exit /b 1
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m karirlog.cli scheduled-run
exit /b %ERRORLEVEL%
