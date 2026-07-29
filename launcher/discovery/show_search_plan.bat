@echo off
setlocal
cd /d "%~dp0\..\.."
set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
"%PYTHON_EXE%" "%CD%\launcher\discovery\show_search_plan.py"
echo.
pause
endlocal
