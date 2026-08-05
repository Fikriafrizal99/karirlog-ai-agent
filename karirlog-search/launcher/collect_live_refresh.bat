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
set "KARIRLOG_BRAVE_CACHE_ONLY=0"
set "REFRESH_SEARCH=1"
set "FORCE_REFRESH=1"
"%PYTHON%" "%ROOT%\main.py" collect --mode live_with_fallback %*
exit /b %ERRORLEVEL%
