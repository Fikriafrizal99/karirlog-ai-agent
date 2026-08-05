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
echo INFO: Membuat Gmail draft saja; email tidak dikirim otomatis.
"%PYTHON%" "%ROOT%\main.py" create-gmail-drafts %*
exit /b %ERRORLEVEL%
