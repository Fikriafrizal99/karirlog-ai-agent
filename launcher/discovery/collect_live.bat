@echo off
setlocal
cd /d "%~dp0\..\.."
set "ROOT=%CD%"
title KarirLog - Live Update
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: virtual environment belum tersedia.
  echo Gunakan menu Setup dan Pemeriksaan untuk install dependencies.
  pause
  exit /b 1
)
if exist "data\output\latest_collection.json" copy /Y "data\output\latest_collection.json" "data\output\latest_collection_previous.json" >nul
set "PYTHONPATH=%ROOT%\src"
set "KARIRLOG_BRAVE_CACHE_ONLY=0"
set "KARIRLOG_BRAVE_REFRESH_SEARCH=1"
set "KARIRLOG_BRAVE_FORCE_REFRESH=0"
echo.
echo LIVE UPDATE: Brave API akan dipanggil untuk pencarian terbaru.
echo Cache halaman detail yang masih valid tetap digunakan agar lebih cepat.
echo.
".venv\Scripts\python.exe" -m karirlog.cli collect --mode live
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" echo LIVE UPDATE SELESAI - PENCARIAN TERBARU DAN CACHE DIPERBARUI.
if not "%RC%"=="0" echo LIVE UPDATE GAGAL.
pause
exit /b %RC%
