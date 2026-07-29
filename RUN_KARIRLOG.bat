@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%CD%"
set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
title KarirLog AI Agent - Control Panel

:MAIN
cls
echo ============================================================
echo              KARIRLOG AI AGENT - CONTROL PANEL
echo ============================================================
echo Project : %ROOT%
echo.
echo [1] OPERASIONAL HARIAN
echo [2] DISCOVERY / PENCARIAN LOWONGAN
echo [3] LAMARAN PORTAL DAN EMAIL
echo [4] STATUS DAN LAPORAN
echo [5] FILE DAN FOLDER PENTING
echo [6] SETUP DAN PEMERIKSAAN
echo [7] TEST DAN MAINTENANCE
echo [0] KELUAR
echo.
choice /c 12345670 /n /m "Pilih menu: "
if errorlevel 8 goto EXIT_APP
if errorlevel 7 goto MAINTENANCE
if errorlevel 6 goto CHECKS
if errorlevel 5 goto FILES
if errorlevel 4 goto STATUS
if errorlevel 3 goto APPLICATIONS
if errorlevel 2 goto DISCOVERY
if errorlevel 1 goto DAILY

goto MAIN

:DAILY
cls
echo ============================================================
echo                    OPERASIONAL HARIAN
echo ============================================================
echo [1] LIVE UPDATE - cari lowongan terbaru sekarang ^(memakai Brave API^)
echo [2] Tinjau diagnostics discovery
echo [3] Analisis live dan buat paket lamaran
echo [4] Lihat status aplikasi terbaru
echo [5] Kirim ringkasan aplikasi ke Telegram
echo [0] Kembali
echo.
choice /c 123450 /n /m "Pilih: "
if errorlevel 6 goto MAIN
if errorlevel 5 (
  call :TELEGRAM_REPORT
  goto DAILY
)
if errorlevel 4 (
  call :LIST_APPLICATIONS
  goto DAILY
)
if errorlevel 3 (
  call :RUN_LIVE
  goto DAILY
)
if errorlevel 2 (
  call "%ROOT%\launcher\discovery\show_discovery_diagnostics.bat"
  goto DAILY
)
if errorlevel 1 (
  call "%ROOT%\launcher\discovery\collect_live.bat"
  goto DAILY
)
goto DAILY

:DISCOVERY
cls
echo ============================================================
echo                 DISCOVERY / PENCARIAN LOWONGAN
echo ============================================================
echo [1] LIVE UPDATE - pencarian Brave terbaru, cache detail tetap digunakan
echo [2] CACHE SAJA - data lama untuk testing, 0 request Brave
echo [3] REFRESH PENUH - pencarian dan halaman detail diunduh ulang
echo [4] Tampilkan diagnostics
echo [5] Ekspor hasil diterima ke CSV review
echo [6] Buka latest_collection.json
echo [7] Lihat 6 sumber discovery aktif
echo [8] Lihat rencana query - 0 request Brave
echo [0] Kembali
echo.
choice /c 123456780 /n /m "Pilih: "
if errorlevel 9 goto MAIN
if errorlevel 8 (
  call "%ROOT%\launcher\discovery\show_search_plan.bat"
  goto DISCOVERY
)
if errorlevel 7 (
  call "%ROOT%\launcher\discovery\show_active_sources.bat"
  goto DISCOVERY
)
if errorlevel 6 (
  call :OPEN_FILE "data\output\latest_collection.json"
  goto DISCOVERY
)
if errorlevel 5 (
  call "%ROOT%\launcher\discovery\export_review_csv.bat"
  goto DISCOVERY
)
if errorlevel 4 (
  call "%ROOT%\launcher\discovery\show_discovery_diagnostics.bat"
  goto DISCOVERY
)
if errorlevel 3 (
  call "%ROOT%\launcher\discovery\collect_live_refresh.bat"
  goto DISCOVERY
)
if errorlevel 2 (
  call "%ROOT%\launcher\discovery\collect_cached.bat"
  goto DISCOVERY
)
if errorlevel 1 (
  call "%ROOT%\launcher\discovery\collect_live.bat"
  goto DISCOVERY
)
goto DISCOVERY

:APPLICATIONS
cls
echo ============================================================
echo                   LAMARAN PORTAL DAN EMAIL
echo ============================================================
echo [1] Login portal melalui browser eksternal
echo [2] Jalankan antrean portal
echo [3] Buka satu aplikasi portal berdasarkan ID
echo [4] Tandai portal sudah submitted
echo [5] Buat draft Gmail dari queue
echo [6] Buat kode approval email
echo [7] Kirim email dengan approval code
echo [8] Kirim laporan Telegram
echo [0] Kembali
echo.
choice /c 123456780 /n /m "Pilih: "
if errorlevel 9 goto MAIN
if errorlevel 8 (
  call :TELEGRAM_REPORT
  goto APPLICATIONS
)
if errorlevel 7 (
  call :SEND_EMAIL
  goto APPLICATIONS
)
if errorlevel 6 (
  call :APPROVE_EMAIL
  goto APPLICATIONS
)
if errorlevel 5 (
  call :CREATE_GMAIL_DRAFTS
  goto APPLICATIONS
)
if errorlevel 4 (
  call :MARK_SUBMITTED
  goto APPLICATIONS
)
if errorlevel 3 (
  call :ASSIST_ONE
  goto APPLICATIONS
)
if errorlevel 2 (
  call :ASSIST_QUEUE
  goto APPLICATIONS
)
if errorlevel 1 (
  call :PORTAL_LOGIN
  goto APPLICATIONS
)
goto APPLICATIONS

:STATUS
cls
echo ============================================================
echo                     STATUS DAN LAPORAN
echo ============================================================
echo [1] Daftar aplikasi terbaru
echo [2] Histori lowongan
echo [3] Audit trail
echo [4] Diagnostics discovery
echo [5] Laporan Telegram
echo [0] Kembali
echo.
choice /c 123450 /n /m "Pilih: "
if errorlevel 6 goto MAIN
if errorlevel 5 (
  call :TELEGRAM_REPORT
  goto STATUS
)
if errorlevel 4 (
  call "%ROOT%\launcher\discovery\show_discovery_diagnostics.bat"
  goto STATUS
)
if errorlevel 3 (
  call :LIST_AUDIT
  goto STATUS
)
if errorlevel 2 (
  call :LIST_JOBS
  goto STATUS
)
if errorlevel 1 (
  call :LIST_APPLICATIONS
  goto STATUS
)
goto STATUS

:FILES
cls
echo ============================================================
echo                    FILE DAN FOLDER PENTING
echo ============================================================
echo [1] Buka hasil discovery terbaru
echo [2] Buka diagnostics discovery
echo [3] Buka folder data output
echo [4] Buka folder application packages
echo [5] Buka folder config
echo [6] Buka folder input
echo [7] Buka folder launcher internal
echo [0] Kembali
echo.
choice /c 12345670 /n /m "Pilih: "
if errorlevel 8 goto MAIN
if errorlevel 7 (
  start "" "%ROOT%\launcher"
  goto FILES
)
if errorlevel 6 (
  start "" "%ROOT%\data\input"
  goto FILES
)
if errorlevel 5 (
  start "" "%ROOT%\config"
  goto FILES
)
if errorlevel 4 (
  if not exist "%ROOT%\data\output\applications" mkdir "%ROOT%\data\output\applications"
  start "" "%ROOT%\data\output\applications"
  goto FILES
)
if errorlevel 3 (
  if not exist "%ROOT%\data\output" mkdir "%ROOT%\data\output"
  start "" "%ROOT%\data\output"
  goto FILES
)
if errorlevel 2 (
  call :OPEN_FILE "data\output\latest_discovery_diagnostics.json"
  goto FILES
)
if errorlevel 1 (
  call :OPEN_FILE "data\output\latest_collection.json"
  goto FILES
)
goto FILES

:CHECKS
cls
echo ============================================================
echo                   SETUP DAN PEMERIKSAAN
echo ============================================================
echo [1] Cek semua integrasi
echo [2] Cek sumber lowongan
echo [3] Cek AI
echo [4] Cek CV dan dokumen
echo [5] Cek Gmail
echo [6] Cek scheduler
echo [7] Install / perbarui dependencies
echo [8] Install Chromium Playwright
echo [0] Kembali
echo.
choice /c 123456780 /n /m "Pilih: "
if errorlevel 9 goto MAIN
if errorlevel 8 (
  call :INSTALL_BROWSER
  goto CHECKS
)
if errorlevel 7 (
  call :INSTALL_DEPS
  goto CHECKS
)
if errorlevel 6 (
  call :RUN_CLI check-scheduler
  goto CHECKS
)
if errorlevel 5 (
  call :RUN_CLI check-gmail
  goto CHECKS
)
if errorlevel 4 (
  call :CHECK_CV_DOCS
  goto CHECKS
)
if errorlevel 3 (
  call :RUN_CLI check-ai
  goto CHECKS
)
if errorlevel 2 (
  call :RUN_CLI check-sources
  goto CHECKS
)
if errorlevel 1 (
  call :CHECK_ALL
  goto CHECKS
)
goto CHECKS

:MAINTENANCE
cls
echo ============================================================
echo                    TEST DAN MAINTENANCE
echo ============================================================
echo [1] Jalankan sample rule-only
echo [2] Jalankan sample AI-required
echo [3] Jalankan sample default
echo [4] Jalankan scheduled pipeline manual
echo [5] Buka backup BAT lama
echo [6] Buka file settings.json
echo [7] Bersihkan data - sisakan PORTAL_SUBMITTED dan EMAIL_SENT
echo [8] Reset total database dan output - HAPUS SEMUA
echo [0] Kembali
echo.
choice /c 123456780 /n /m "Pilih: "
if errorlevel 9 goto MAIN
if errorlevel 8 (
  call :RESET_DATA
  goto MAINTENANCE
)
if errorlevel 7 (
  call :CLEAN_KEEP_SUBMITTED
  goto MAINTENANCE
)
if errorlevel 6 (
  call :OPEN_FILE "config\settings.json"
  goto MAINTENANCE
)
if errorlevel 5 (
  if not exist "%ROOT%\launcher\maintenance\legacy_root" mkdir "%ROOT%\launcher\maintenance\legacy_root"
  start "" "%ROOT%\launcher\maintenance\legacy_root"
  goto MAINTENANCE
)
if errorlevel 4 (
  call "%ROOT%\launcher\scheduler\scheduled_run.bat"
  pause
  goto MAINTENANCE
)
if errorlevel 3 (
  call :RUN_CLI run --mode sample
  goto MAINTENANCE
)
if errorlevel 2 (
  call :RUN_CLI run --mode sample --analysis-mode ai_required
  goto MAINTENANCE
)
if errorlevel 1 (
  call :RUN_CLI run --mode sample --analysis-mode rule_only
  goto MAINTENANCE
)
goto MAINTENANCE

:ENSURE_ENV
if exist "%PYTHON_EXE%" (
  set "PYTHONPATH=%ROOT%\src"
  exit /b 0
)
echo.
echo Virtual environment belum tersedia.
echo Menjalankan instalasi dependencies terlebih dahulu...
call :INSTALL_DEPS
if not exist "%PYTHON_EXE%" exit /b 1
set "PYTHONPATH=%ROOT%\src"
exit /b 0

:RUN_CLI
call :ENSURE_ENV
if errorlevel 1 exit /b 1
echo.
"%PYTHON_EXE%" -m karirlog.cli %*
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Perintah selesai dengan error code %RC%.
pause
exit /b %RC%

:RUN_LIVE
call :RUN_CLI run --mode live
exit /b %ERRORLEVEL%

:LIST_APPLICATIONS
call :RUN_CLI list-applications --limit 50
exit /b %ERRORLEVEL%

:LIST_JOBS
call :RUN_CLI list --limit 50
exit /b %ERRORLEVEL%

:LIST_AUDIT
call :RUN_CLI list-audit --limit 100
exit /b %ERRORLEVEL%

:TELEGRAM_REPORT
set "LIMIT=50"
set /p "LIMIT=Jumlah aplikasi yang dilaporkan [50]: "
if not defined LIMIT set "LIMIT=50"
call :RUN_CLI telegram-application-report --limit %LIMIT%
exit /b %ERRORLEVEL%

:PORTAL_LOGIN
call :RUN_CLI portal-login
exit /b %ERRORLEVEL%

:ASSIST_QUEUE
set "LIMIT=100"
set /p "LIMIT=Batas antrean portal [100]: "
if not defined LIMIT set "LIMIT=100"
call :RUN_CLI assist-portal-queue --limit %LIMIT%
exit /b %ERRORLEVEL%

:ASSIST_ONE
set "APP_ID="
set /p "APP_ID=Masukkan application ID tanpa tanda #: "
if not defined APP_ID exit /b 0
call :RUN_CLI assist-portal --application-id %APP_ID%
exit /b %ERRORLEVEL%

:MARK_SUBMITTED
set "APP_ID="
set /p "APP_ID=Masukkan application ID yang sudah submitted: "
if not defined APP_ID exit /b 0
call :RUN_CLI mark-portal-submitted --application-id %APP_ID%
exit /b %ERRORLEVEL%

:CREATE_GMAIL_DRAFTS
set "LIMIT=10"
set /p "LIMIT=Maksimal draft Gmail [10]: "
if not defined LIMIT set "LIMIT=10"
call :RUN_CLI create-gmail-drafts --limit %LIMIT%
exit /b %ERRORLEVEL%

:APPROVE_EMAIL
set "APP_ID="
set /p "APP_ID=Masukkan application ID email: "
if not defined APP_ID exit /b 0
call :RUN_CLI approve-email --application-id %APP_ID%
exit /b %ERRORLEVEL%

:SEND_EMAIL
set "APP_ID="
set "APP_CODE="
set /p "APP_ID=Masukkan application ID email: "
if not defined APP_ID exit /b 0
set /p "APP_CODE=Masukkan approval code: "
if not defined APP_CODE exit /b 0
call :RUN_CLI send-email --application-id %APP_ID% --confirm %APP_CODE%
exit /b %ERRORLEVEL%

:CHECK_CV_DOCS
call :ENSURE_ENV
if errorlevel 1 exit /b 1
echo.
"%PYTHON_EXE%" -m karirlog.cli check-cv
echo.
"%PYTHON_EXE%" -m karirlog.cli check-documents
pause
exit /b 0

:CHECK_ALL
call :ENSURE_ENV
if errorlevel 1 exit /b 1
for %%C in (check-sources check-ai check-cv check-documents check-gmail check-scheduler) do (
  echo.
  echo ===== %%C =====
  "%PYTHON_EXE%" -m karirlog.cli %%C
)
echo.
pause
exit /b 0

:INSTALL_DEPS
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 (
    echo Gagal membuat virtual environment.
    pause
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo Dependencies siap.) else (echo Instalasi dependencies gagal.)
pause
exit /b %RC%

:INSTALL_BROWSER
call :ENSURE_ENV
if errorlevel 1 exit /b 1
"%PYTHON_EXE%" -m playwright install chromium
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (echo Chromium Playwright siap.) else (echo Instalasi Chromium gagal.)
pause
exit /b %RC%

:OPEN_FILE
set "TARGET=%~1"
if not exist "%ROOT%\%TARGET%" (
  echo.
  echo File belum tersedia: %TARGET%
  pause
  exit /b 1
)
start "" "%ROOT%\%TARGET%"
exit /b 0

:CLEAN_KEEP_SUBMITTED
call :ENSURE_ENV
if errorlevel 1 exit /b 1
echo.
"%PYTHON_EXE%" "%ROOT%\launcher\maintenance\cleanup_keep_submitted.py"
echo.
set "CONFIRM_CLEAN="
echo PERINGATAN: draft, review, gagal, histori pencarian, cache, dan output non-submit akan dihapus.
set /p "CONFIRM_CLEAN=Ketik BERSIHKAN untuk melanjutkan: "
if /I not "%CONFIRM_CLEAN%"=="BERSIHKAN" (
  echo Dibatalkan. Tidak ada data yang diubah.
  pause
  exit /b 0
)
echo.
"%PYTHON_EXE%" "%ROOT%\launcher\maintenance\cleanup_keep_submitted.py" --apply
set "RC=%ERRORLEVEL%"
echo.
if not "%RC%"=="0" echo Pembersihan gagal dengan error code %RC%.
pause
exit /b %RC%

:RESET_DATA
set "CONFIRM_RESET="
echo.
echo PERINGATAN: tindakan ini dapat menghapus database dan output test.
set /p "CONFIRM_RESET=Ketik RESET untuk melanjutkan: "
if /I not "%CONFIRM_RESET%"=="RESET" (
  echo Dibatalkan.
  pause
  exit /b 0
)
call :RUN_CLI reset
exit /b %ERRORLEVEL%

:EXIT_APP
cls
echo KarirLog ditutup.
endlocal
exit /b 0
