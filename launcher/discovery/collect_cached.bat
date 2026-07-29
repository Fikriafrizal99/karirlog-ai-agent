@echo off
setlocal
cd /d "%~dp0\..\.."
set "ROOT=%CD%"
title KarirLog - Cache Only
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: virtual environment belum tersedia.
  echo Gunakan menu Setup dan Pemeriksaan untuk install dependencies.
  pause
  exit /b 1
)
if exist "data\output\latest_collection.json" copy /Y "data\output\latest_collection.json" "data\output\latest_collection_previous.json" >nul
set "PYTHONPATH=%ROOT%\src"
set "KARIRLOG_BRAVE_CACHE_ONLY=1"
set "KARIRLOG_BRAVE_REFRESH_SEARCH=0"
set "KARIRLOG_BRAVE_FORCE_REFRESH=0"
echo.
echo CACHE SAJA: tidak mencari lowongan terbaru dan tidak memakai Brave API.
echo Mode ini hanya untuk testing parser, filter, atau pemeriksaan ulang.
echo.
".venv\Scripts\python.exe" -m karirlog.cli collect --mode live
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" echo CACHE COLLECTION SELESAI - API BRAVE BARU = 0.
if not "%RC%"=="0" echo CACHE COLLECTION GAGAL. Cache mungkin belum tersedia.
pause
exit /b %RC%
