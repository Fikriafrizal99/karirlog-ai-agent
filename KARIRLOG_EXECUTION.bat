@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "EXEC_ROOT=%ROOT%\karirlog-execution"
set "EXEC_PY=%EXEC_ROOT%\.venv\Scripts\python.exe"
title KarirLog - Execution Modes

rem Existing callers that pass flags keep the old direct behavior.
if not "%~1"=="" goto DIRECT

:MENU
cls
echo ============================================================
echo                    KARIRLOG EXECUTION MODE
echo ============================================================
echo [1] AI FULL APPLY
echo     OpenAI + rule fallback, lalu Gmail / Portal
echo.
echo [2] RULE ONLY FULL APPLY
echo     OpenAI OFF, rule engine tetap menilai APPLY / REVIEW / SKIP
echo.
echo [3] TRUSTED CSV - PORTAL ONLY [RECOMMENDED]
echo     AI OFF + Rule OFF, semua baris CSV = APPLY, Portal max 100
echo.
echo [4] TRUSTED CSV - FORCE REPROCESS + REBUILD
echo     Sama seperti [3], tapi proses ulang job yang pernah masuk KarirLog
echo.
echo [5] TRUSTED CSV - BUILD PACKAGE ONLY
echo     AI OFF + Rule OFF, buat package tanpa Gmail / buka Portal
echo.
echo [6] LANJUTKAN PORTAL QUEUE - MAX 100
echo     Tanpa analisis ulang
echo.
echo [0] KEMBALI
echo ============================================================
echo.
choice /c 1234560 /n /m "Pilih mode: "
if errorlevel 7 goto EXIT_MENU
if errorlevel 6 goto PORTAL_QUEUE
if errorlevel 5 goto TRUSTED_BUILD
if errorlevel 4 goto TRUSTED_FORCE
if errorlevel 3 goto TRUSTED_PORTAL
if errorlevel 2 goto RULE_FULL
if errorlevel 1 goto AI_FULL
goto MENU

:AI_FULL
call :RUN_ASSISTANT --analysis-mode ai_with_fallback
goto MENU

:RULE_FULL
call :RUN_ASSISTANT --analysis-mode rule_only
goto MENU

:TRUSTED_PORTAL
call :RUN_ASSISTANT --analysis-mode trusted_csv --portal-only --skip-gmail --portal-limit 100
goto MENU

:TRUSTED_FORCE
call :RUN_ASSISTANT --analysis-mode trusted_csv --portal-only --skip-gmail --portal-limit 100 --force-reprocess --rebuild-packages
goto MENU

:TRUSTED_BUILD
call :RUN_ASSISTANT --analysis-mode trusted_csv --portal-only --skip-gmail --skip-portal
goto MENU

:PORTAL_QUEUE
call :CHECK_EXEC_PY
if errorlevel 1 goto MENU
pushd "%EXEC_ROOT%"
"%EXEC_PY%" main.py assist-portal-queue --limit 100
set "EXIT_CODE=%ERRORLEVEL%"
popd
echo.
pause
goto MENU

:RUN_ASSISTANT
call :CHECK_EXEC_PY
if errorlevel 1 exit /b 2
pushd "%EXEC_ROOT%"
"%EXEC_PY%" apply_assistant.py %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
echo.
pause
exit /b %EXIT_CODE%

:CHECK_EXEC_PY
if exist "%EXEC_PY%" exit /b 0
echo.
echo ERROR: Execution virtual environment belum tersedia.
echo Jalankan KARIRLOG_MENU.bat ^> SYSTEM / SETTINGS ^> SETUP / INSTALL ^> Setup Execution Environment.
echo.
pause
exit /b 2

:DIRECT
rem Backward compatibility for KARIRLOG_MENU.bat actions such as
rem --force-reprocess and --rebuild-packages.
call "%EXEC_ROOT%\launcher\execute_latest.bat" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
pause
exit /b %EXIT_CODE%

:EXIT_MENU
exit /b 0
