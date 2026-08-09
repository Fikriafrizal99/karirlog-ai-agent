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
set "INPUT=%ROOT%\data\input\discovery_latest.csv"
if not exist "%INPUT%" (
  echo ERROR: CSV handoff manual tidak ditemukan.
  echo.
  echo Review hasil Search di Excel, lalu simpan/copy sebagai:
  echo   %INPUT%
  echo.
  echo Execution sengaja tidak membaca langsung dari folder Search.
  exit /b 2
)
echo Input manual: %INPUT%
"%PYTHON%" "%ROOT%\apply_assistant.py" --input "%INPUT%" %*
exit /b %ERRORLEVEL%
