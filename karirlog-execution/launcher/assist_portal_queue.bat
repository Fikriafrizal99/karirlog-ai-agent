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
echo INFO: Portal assistant manual-only; tidak submit otomatis tanpa konfirmasi.
"%PYTHON%" "%ROOT%\main.py" assist-portal-queue %*
exit /b %ERRORLEVEL%
