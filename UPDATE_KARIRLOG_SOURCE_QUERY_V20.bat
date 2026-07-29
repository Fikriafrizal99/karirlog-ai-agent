@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
"%PYTHON_EXE%" "%CD%\update_karirlog_source_query_v20.py"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
  echo.
  echo UPDATE GAGAL. File updater tidak dihapus.
  pause
  exit /b %RESULT%
)
echo.
echo Update selesai. File installer sementara akan dibersihkan.
if exist "%CD%\payload" rmdir /s /q "%CD%\payload"
del /q "%CD%\update_karirlog_source_query_v20.py" >nul 2>&1
del /q "%CD%\KARIRLOG_SOURCE_QUERY_V20_RELEASE_NOTES.md" >nul 2>&1
start "" cmd /c "timeout /t 1 /nobreak >nul & del /q \"%~f0\""
endlocal
exit /b 0
