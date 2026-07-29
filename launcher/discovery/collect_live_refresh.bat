@echo off
setlocal
cd /d "%~dp0\..\.."
set "ROOT=%CD%"
title KarirLog - Full Refresh
set "CONFIRM="
echo REFRESH PENUH akan memanggil Brave API dan mengunduh ulang halaman detail.
echo Gunakan hanya saat cache rusak atau hasil live tidak sesuai.
set /p "CONFIRM=Ketik REFRESH untuk melanjutkan: "
if /I not "%CONFIRM%"=="REFRESH" (
  echo Dibatalkan.
  pause
  exit /b 0
)
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: virtual environment belum tersedia.
  pause
  exit /b 1
)
if exist "data\output\latest_collection.json" copy /Y "data\output\latest_collection.json" "data\output\latest_collection_previous.json" >nul
set "PYTHONPATH=%ROOT%\src"
set "KARIRLOG_BRAVE_CACHE_ONLY=0"
set "KARIRLOG_BRAVE_REFRESH_SEARCH=1"
set "KARIRLOG_BRAVE_FORCE_REFRESH=1"
".venv\Scripts\python.exe" -m karirlog.cli collect --mode live
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" echo REFRESH PENUH SELESAI - PENCARIAN DAN HALAMAN DETAIL DIPERBARUI.
if not "%RC%"=="0" echo REFRESH PENUH GAGAL.
pause
exit /b %RC%
