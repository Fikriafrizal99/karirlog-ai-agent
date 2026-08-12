@echo off
setlocal
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERROR: Search .venv belum dibuat.
  exit /b 2
)
cd /d "%ROOT%"
"%PYTHON%" "%ROOT%\main.py" show-plan %*
exit /b %ERRORLEVEL%
