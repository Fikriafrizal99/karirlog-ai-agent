@echo off
setlocal
set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
if not exist "%ROOT%\data\output" mkdir "%ROOT%\data\output"
start "KarirLog Search output" explorer.exe "%ROOT%\data\output"
exit /b 0
