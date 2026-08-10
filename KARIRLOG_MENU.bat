@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "ROOT=%~dp0"
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "EXEC_ROOT=%ROOT%\karirlog-execution"
set "SEARCH_ROOT=%ROOT%\karirlog-search"
set "EXEC_PY=%EXEC_ROOT%\.venv\Scripts\python.exe"
set "SEARCH_PY=%SEARCH_ROOT%\.venv\Scripts\python.exe"
set "TOOL=%ROOT%\karirlog-tools\control.py"
title KarirLog - Main Menu

:MAIN
cls
echo ============================================================
echo                    KARIRLOG MAIN MENU
echo ============================================================
echo [1] QUICK START
echo [2] SEARCH LOWONGAN
echo [3] EXECUTION / APPLY
echo [4] REPORT
echo [5] TELEGRAM
echo [6] GMAIL
echo [7] JOB PORTAL
echo [8] CV DAN PROFILE
echo [9] SYSTEM / SETTINGS
echo [0] KELUAR
echo.
choice /c 1234567890 /n /m "Pilih menu: "
if errorlevel 10 goto EXIT_APP
if errorlevel 9 goto SYSTEM
if errorlevel 8 goto CVPROFILE
if errorlevel 7 goto PORTAL
if errorlevel 6 goto GMAIL
if errorlevel 5 goto TELEGRAM
if errorlevel 4 goto REPORT
if errorlevel 3 goto EXECUTION
if errorlevel 2 goto SEARCH
if errorlevel 1 goto QUICK
goto MAIN

:QUICK
cls
echo ============================================================
echo                         QUICK START
echo ============================================================
echo [1] Cari lowongan baru
echo [2] Proses CSV yang sudah direview dan bantu apply
echo [3] Lanjutkan lamaran pending tanpa analisis ulang
echo [4] Buka CSV hasil Search
echo [5] Buka folder input Execution
echo [0] Kembali
echo.
choice /c 123450 /n /m "Pilih: "
if errorlevel 6 goto MAIN
if errorlevel 5 (
  call :OPEN_DIR "%EXEC_ROOT%\data\input"
  goto QUICK
)
if errorlevel 4 (
  call :OPEN_FILE "%SEARCH_ROOT%\data\output\discovery_latest.csv"
  goto QUICK
)
if errorlevel 3 (
  call :CONTINUE_PENDING
  goto QUICK
)
if errorlevel 2 (
  call "%ROOT%\KARIRLOG_EXECUTION.bat"
  goto QUICK
)
if errorlevel 1 (
  call "%ROOT%\KARIRLOG_SEARCH.bat"
  goto QUICK
)
goto QUICK

:SEARCH
cls
echo ============================================================
echo                       SEARCH LOWONGAN
echo ============================================================
echo [1] Live Search - Brave API
echo [2] Cache Only - 0 request Brave
echo [3] Full Refresh - Brave + refresh halaman detail
echo [4] Lihat rencana query - 0 request Brave
echo [5] Cek sumber Search
echo [6] Buka CSV hasil Search
echo [7] Buka folder output Search
echo [0] Kembali
echo.
choice /c 12345670 /n /m "Pilih: "
if errorlevel 8 goto MAIN
if errorlevel 7 (
  call :OPEN_DIR "%SEARCH_ROOT%\data\output"
  goto SEARCH
)
if errorlevel 6 (
  call :OPEN_FILE "%SEARCH_ROOT%\data\output\discovery_latest.csv"
  goto SEARCH
)
if errorlevel 5 (
  call "%SEARCH_ROOT%\launcher\check_sources.bat"
  pause
  goto SEARCH
)
if errorlevel 4 (
  call "%SEARCH_ROOT%\launcher\show_search_plan.bat"
  pause
  goto SEARCH
)
if errorlevel 3 (
  call "%SEARCH_ROOT%\launcher\collect_live_refresh.bat"
  pause
  goto SEARCH
)
if errorlevel 2 (
  call "%SEARCH_ROOT%\launcher\collect_cached.bat"
  pause
  goto SEARCH
)
if errorlevel 1 (
  call "%ROOT%\KARIRLOG_SEARCH.bat"
  goto SEARCH
)
goto SEARCH

:EXECUTION
cls
echo ============================================================
echo                      EXECUTION / APPLY
echo ============================================================
echo [1] Full Apply Assistant
echo [2] Analisis saja - tanpa Gmail dan Portal
echo [3] Force reprocess CSV
echo [4] Rebuild application package
echo [5] Lanjutkan pending Gmail + Portal
echo [6] Buka folder input Execution
echo [7] Buka folder output Execution
echo [0] Kembali
echo.
choice /c 12345670 /n /m "Pilih: "
if errorlevel 8 goto MAIN
if errorlevel 7 (
  call :OPEN_DIR "%EXEC_ROOT%\data\output"
  goto EXECUTION
)
if errorlevel 6 (
  call :OPEN_DIR "%EXEC_ROOT%\data\input"
  goto EXECUTION
)
if errorlevel 5 (
  call :CONTINUE_PENDING
  goto EXECUTION
)
if errorlevel 4 (
  call "%ROOT%\KARIRLOG_EXECUTION.bat" --rebuild-packages
  goto EXECUTION
)
if errorlevel 3 (
  call "%ROOT%\KARIRLOG_EXECUTION.bat" --force-reprocess
  goto EXECUTION
)
if errorlevel 2 (
  call :RUN_APPLY_ASSISTANT --skip-gmail --skip-portal
  goto EXECUTION
)
if errorlevel 1 (
  call "%ROOT%\KARIRLOG_EXECUTION.bat"
  goto EXECUTION
)
goto EXECUTION

:REPORT
cls
echo ============================================================
echo                           REPORT
echo ============================================================
echo [1] Daftar aplikasi terbaru
echo [2] Daftar job dan hasil APPLY / REVIEW / SKIP
echo [3] Audit trail
echo [4] Kirim application report ke Telegram
echo [5] Buka output Execution
echo [6] Buka output Search
echo [7] Buka diagnostics Search
echo [0] Kembali
echo.
choice /c 12345670 /n /m "Pilih: "
if errorlevel 8 goto MAIN
if errorlevel 7 (
  call :OPEN_FILE "%SEARCH_ROOT%\data\output\latest_discovery_diagnostics.json"
  goto REPORT
)
if errorlevel 6 (
  call :OPEN_DIR "%SEARCH_ROOT%\data\output"
  goto REPORT
)
if errorlevel 5 (
  call :OPEN_DIR "%EXEC_ROOT%\data\output"
  goto REPORT
)
if errorlevel 4 (
  call :RUN_EXEC telegram-application-report --limit 50
  goto REPORT
)
if errorlevel 3 (
  call :RUN_EXEC list-audit --limit 100
  goto REPORT
)
if errorlevel 2 (
  call :RUN_EXEC list --limit 50
  goto REPORT
)
if errorlevel 1 (
  call :RUN_EXEC list-applications --limit 50
  goto REPORT
)
goto REPORT

:TELEGRAM
cls
echo ============================================================
echo                          TELEGRAM
echo ============================================================
echo [1] Cek status konfigurasi Telegram
echo [2] Set / Sync Telegram ke Search + Execution
echo [3] Kirim test message
echo [4] Buka Search .env
echo [5] Buka Execution .env
echo [6] Kirim application report terbaru
echo [7] Buka Search .env.example
echo [8] Buka Execution .env.example
echo [0] Kembali
echo.
choice /c 123456780 /n /m "Pilih: "
if errorlevel 9 goto MAIN
if errorlevel 8 (
  call :OPEN_FILE "%EXEC_ROOT%\.env.example"
  goto TELEGRAM
)
if errorlevel 7 (
  call :OPEN_FILE "%SEARCH_ROOT%\.env.example"
  goto TELEGRAM
)
if errorlevel 6 (
  call :RUN_EXEC telegram-application-report --limit 50
  goto TELEGRAM
)
if errorlevel 5 (
  call :OPEN_ENV "%EXEC_ROOT%\.env" "%EXEC_ROOT%\.env.example"
  goto TELEGRAM
)
if errorlevel 4 (
  call :OPEN_ENV "%SEARCH_ROOT%\.env" "%SEARCH_ROOT%\.env.example"
  goto TELEGRAM
)
if errorlevel 3 (
  call :RUN_TOOL telegram-test
  goto TELEGRAM
)
if errorlevel 2 (
  call :RUN_TOOL telegram-config
  goto TELEGRAM
)
if errorlevel 1 (
  call :RUN_TOOL telegram-status
  goto TELEGRAM
)
goto TELEGRAM

:GMAIL
cls
echo ============================================================
echo                            GMAIL
echo ============================================================
echo [1] Cek koneksi Gmail
echo [2] Buat draft Gmail pending
echo [3] Lihat status aplikasi
echo [4] Buka Gmail di browser
echo [5] Buka folder untuk credentials.json
echo [0] Kembali
echo.
choice /c 123450 /n /m "Pilih: "
if errorlevel 6 goto MAIN
if errorlevel 5 (
  call :OPEN_DIR "%EXEC_ROOT%"
  goto GMAIL
)
if errorlevel 4 (
  start "" "https://mail.google.com/"
  goto GMAIL
)
if errorlevel 3 (
  call :RUN_EXEC list-applications --limit 50
  goto GMAIL
)
if errorlevel 2 (
  call :RUN_EXEC create-gmail-drafts --limit 10
  goto GMAIL
)
if errorlevel 1 (
  call :RUN_EXEC check-gmail
  goto GMAIL
)
goto GMAIL

:PORTAL
cls
echo ============================================================
echo                         JOB PORTAL
echo ============================================================
echo [1] Buka / cek login browser KarirLog
echo [2] Lanjutkan portal queue
echo [3] Lihat status aplikasi
echo [4] Tandai application sudah submitted
echo [5] Buka folder report portal
echo [0] Kembali
echo.
choice /c 123450 /n /m "Pilih: "
if errorlevel 6 goto MAIN
if errorlevel 5 (
  call :OPEN_DIR "%EXEC_ROOT%\data\output\portal_sessions"
  goto PORTAL
)
if errorlevel 4 (
  set "APP_ID="
  set /p "APP_ID=Application ID: "
  if defined APP_ID call :RUN_EXEC mark-portal-submitted --application-id !APP_ID!
  goto PORTAL
)
if errorlevel 3 (
  call :RUN_EXEC list-applications --limit 50
  goto PORTAL
)
if errorlevel 2 (
  call :RUN_EXEC assist-portal-queue --limit 50
  goto PORTAL
)
if errorlevel 1 (
  call :RUN_EXEC portal-login
  goto PORTAL
)
goto PORTAL

:CVPROFILE
cls
echo ============================================================
echo                       CV DAN PROFILE
echo ============================================================
echo [1] Cek CV library
echo [2] Cek document library
echo [3] Buka folder CV
echo [4] Buka candidate_profile.json
echo [5] Buka cv_library.json
echo [6] Buat candidate profile dari template
echo [0] Kembali
echo.
choice /c 1234560 /n /m "Pilih: "
if errorlevel 7 goto MAIN
if errorlevel 6 (
  call :INIT_PROFILE
  goto CVPROFILE
)
if errorlevel 5 (
  call :OPEN_FILE "%EXEC_ROOT%\config\cv_library.json"
  goto CVPROFILE
)
if errorlevel 4 (
  call :OPEN_FILE "%EXEC_ROOT%\config\candidate_profile.json"
  goto CVPROFILE
)
if errorlevel 3 (
  call :OPEN_DIR "%EXEC_ROOT%\documents\cv"
  goto CVPROFILE
)
if errorlevel 2 (
  call :RUN_EXEC check-documents
  goto CVPROFILE
)
if errorlevel 1 (
  call :RUN_EXEC check-cv
  goto CVPROFILE
)
goto CVPROFILE

:SYSTEM
cls
echo ============================================================
echo                      SYSTEM / SETTINGS
echo ============================================================
echo [1] System status
echo [2] API Usage / Cost Audit
echo [3] Cek AI
echo [4] Cek Search sources
echo [5] Buka Search sources.json
echo [6] Buka Execution settings.json
echo [7] Buka folder project
echo [8] SETUP / INSTALL
echo [9] Buka menu lama RUN_KARIRLOG.bat
echo [0] Kembali
echo.
choice /c 1234567890 /n /m "Pilih: "
if errorlevel 10 goto MAIN
if errorlevel 9 (
  if exist "%ROOT%\RUN_KARIRLOG.bat" start "" "%ROOT%\RUN_KARIRLOG.bat"
  goto SYSTEM
)
if errorlevel 8 goto SETUP
if errorlevel 7 (
  start "" "%ROOT%"
  goto SYSTEM
)
if errorlevel 6 (
  call :OPEN_FILE "%EXEC_ROOT%\config\execution_settings.json"
  goto SYSTEM
)
if errorlevel 5 (
  call :OPEN_FILE "%SEARCH_ROOT%\config\sources.json"
  goto SYSTEM
)
if errorlevel 4 (
  call "%SEARCH_ROOT%\launcher\check_sources.bat"
  pause
  goto SYSTEM
)
if errorlevel 3 (
  call :RUN_EXEC check-ai
  goto SYSTEM
)
if errorlevel 2 (
  set "JOB_COUNT=30"
  set /p "JOB_COUNT=Perkiraan jumlah job yang dianalisis AI [30]: "
  if not defined JOB_COUNT set "JOB_COUNT=30"
  call :RUN_TOOL api-audit --jobs !JOB_COUNT!
  goto SYSTEM
)
if errorlevel 1 (
  call :RUN_TOOL status
  goto SYSTEM
)
goto SYSTEM

:SETUP
cls
echo ============================================================
echo                       SETUP / INSTALL
echo ============================================================
echo [1] Setup Search Environment
echo [2] Setup Execution Environment
echo [3] Setup Keduanya
echo [4] Set / Update OpenAI API Key
echo [5] Set / Sync Telegram
echo [6] Buat Candidate Profile dari template
echo [7] Buka folder CV
echo [8] Install Playwright Chromium
echo [9] Cek semua status
echo [0] Kembali
echo.
choice /c 1234567890 /n /m "Pilih: "
if errorlevel 10 goto SYSTEM
if errorlevel 9 (
  call :RUN_TOOL status
  goto SETUP
)
if errorlevel 8 (
  call :INSTALL_BROWSER
  goto SETUP
)
if errorlevel 7 (
  call :OPEN_DIR "%EXEC_ROOT%\documents\cv"
  goto SETUP
)
if errorlevel 6 (
  call :INIT_PROFILE
  goto SETUP
)
if errorlevel 5 (
  call :RUN_TOOL telegram-config
  goto SETUP
)
if errorlevel 4 (
  call :RUN_TOOL openai-config
  goto SETUP
)
if errorlevel 3 (
  call :SETUP_SEARCH_ENV
  if errorlevel 1 goto SETUP
  call :SETUP_EXEC_ENV
  goto SETUP
)
if errorlevel 2 (
  call :SETUP_EXEC_ENV
  goto SETUP
)
if errorlevel 1 (
  call :SETUP_SEARCH_ENV
  goto SETUP
)
goto SETUP

:CONTINUE_PENDING
echo.
echo Melanjutkan queue tanpa analisis ulang...
call :RUN_EXEC create-gmail-drafts --limit 10
call :RUN_EXEC assist-portal-queue --limit 50
exit /b 0

:SETUP_SEARCH_ENV
echo.
echo ============================================================
echo SETUP SEARCH ENVIRONMENT
echo ============================================================
if not exist "%SEARCH_PY%" (
  echo Membuat Search .venv...
  py -3 -m venv "%SEARCH_ROOT%\.venv"
  if errorlevel 1 (
    echo ERROR: gagal membuat Search .venv. Pastikan Python tersedia melalui command py -3.
    pause
    exit /b 2
  )
) else (
  echo Search .venv sudah ada. Tidak dihapus.
)
pushd "%SEARCH_ROOT%"
"%SEARCH_PY%" -m pip install --upgrade pip
if errorlevel 1 (
  popd
  echo ERROR: gagal upgrade pip Search.
  pause
  exit /b 2
)
"%SEARCH_PY%" -m pip install -r requirements.txt
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" (
  echo ERROR: instalasi dependency Search gagal.
  pause
  exit /b %RC%
)
echo Search environment READY.
pause
exit /b 0

:SETUP_EXEC_ENV
echo.
echo ============================================================
echo SETUP EXECUTION ENVIRONMENT
echo ============================================================
if not exist "%EXEC_PY%" (
  echo Membuat Execution .venv...
  py -3 -m venv "%EXEC_ROOT%\.venv"
  if errorlevel 1 (
    echo ERROR: gagal membuat Execution .venv. Pastikan Python tersedia melalui command py -3.
    pause
    exit /b 2
  )
) else (
  echo Execution .venv sudah ada. Tidak dihapus.
)
pushd "%EXEC_ROOT%"
"%EXEC_PY%" -m pip install --upgrade pip
if errorlevel 1 (
  popd
  echo ERROR: gagal upgrade pip Execution.
  pause
  exit /b 2
)
"%EXEC_PY%" -m pip install -r requirements.txt
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" (
  echo ERROR: instalasi dependency Execution gagal.
  pause
  exit /b %RC%
)
echo Execution environment READY.
pause
exit /b 0

:INSTALL_BROWSER
if not exist "%EXEC_PY%" (
  echo ERROR: setup Execution Environment dulu.
  pause
  exit /b 2
)
"%EXEC_PY%" -m playwright install chromium
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" (echo Playwright Chromium READY.) else (echo ERROR: instalasi Chromium gagal.)
pause
exit /b %RC%

:INIT_PROFILE
set "PROFILE=%EXEC_ROOT%\config\candidate_profile.json"
set "PROFILE_EXAMPLE=%EXEC_ROOT%\config\candidate_profile.example.json"
if exist "%PROFILE%" (
  echo Candidate profile sudah ada. File tidak ditimpa.
  start "" notepad.exe "%PROFILE%"
  exit /b 0
)
if not exist "%PROFILE_EXAMPLE%" (
  echo ERROR: candidate_profile.example.json tidak ditemukan.
  pause
  exit /b 2
)
copy /y "%PROFILE_EXAMPLE%" "%PROFILE%" >nul
echo Candidate profile dibuat dari template.
echo Isi data pribadi lalu simpan. File ini di-ignore Git.
start "" notepad.exe "%PROFILE%"
exit /b 0

:RUN_APPLY_ASSISTANT
if not exist "%EXEC_PY%" (
  echo ERROR: Execution .venv belum tersedia.
  echo Buka SYSTEM / SETTINGS ^> SETUP / INSTALL ^> Setup Execution Environment.
  pause
  exit /b 2
)
pushd "%EXEC_ROOT%"
"%EXEC_PY%" "%EXEC_ROOT%\apply_assistant.py" %*
set "RC=%ERRORLEVEL%"
popd
echo.
pause
exit /b %RC%

:RUN_EXEC
if not exist "%EXEC_PY%" (
  echo ERROR: Execution .venv belum tersedia.
  echo Buka SYSTEM / SETTINGS ^> SETUP / INSTALL ^> Setup Execution Environment.
  pause
  exit /b 2
)
pushd "%EXEC_ROOT%"
"%EXEC_PY%" "%EXEC_ROOT%\main.py" %*
set "RC=%ERRORLEVEL%"
popd
echo.
pause
exit /b %RC%

:RUN_TOOL
set "TOOL_PY="
if exist "%EXEC_PY%" set "TOOL_PY=%EXEC_PY%"
if not defined TOOL_PY if exist "%SEARCH_PY%" set "TOOL_PY=%SEARCH_PY%"
if defined TOOL_PY (
  "%TOOL_PY%" "%TOOL%" %*
) else (
  py -3 "%TOOL%" %*
)
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%

:OPEN_ENV
set "ENV_TARGET=%~1"
set "ENV_EXAMPLE=%~2"
if exist "%ENV_TARGET%" (
  start "" notepad.exe "%ENV_TARGET%"
) else (
  echo File .env belum ada.
  if exist "%ENV_EXAMPLE%" (
    echo Membuka contoh: %ENV_EXAMPLE%
    start "" notepad.exe "%ENV_EXAMPLE%"
  ) else (
    echo Contoh .env juga tidak ditemukan.
    pause
  )
)
exit /b 0

:OPEN_FILE
if exist "%~1" (
  start "" "%~1"
) else (
  echo File belum tersedia:
  echo %~1
  pause
)
exit /b 0

:OPEN_DIR
if not exist "%~1" mkdir "%~1" >nul 2>nul
start "" "%~1"
exit /b 0

:EXIT_APP
endlocal
exit /b 0
