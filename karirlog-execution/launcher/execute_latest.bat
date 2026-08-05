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
set "INPUT=%ROOT%\..\karirlog-search\data\output\discovery_latest.csv"
if not exist "%INPUT%" set "INPUT=%ROOT%\data\input\discovery_latest.csv"
if not exist "%INPUT%" (
  echo ERROR: CSV handoff tidak ditemukan. Jalankan Search atau siapkan data\input\discovery_latest.csv.
  exit /b 2
)
"%PYTHON%" "%ROOT%\main.py" execute --input "%INPUT%" %*
exit /b %ERRORLEVEL%
