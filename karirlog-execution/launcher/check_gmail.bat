@echo off
setlocal
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo ERROR: Execution .venv belum dibuat.
  exit /b 2
)
cd /d "%ROOT%"
"%PYTHON%" "%ROOT%\main.py" check-gmail %*
exit /b %ERRORLEVEL%
