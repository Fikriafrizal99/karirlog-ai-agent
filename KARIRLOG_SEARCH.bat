@echo off
setlocal
set "ROOT=%~dp0"
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
call "%ROOT%\karirlog-search\launcher\collect_live.bat" %*
set "EXIT_CODE=%ERRORLEVEL%"
echo.
pause
exit /b %EXIT_CODE%
