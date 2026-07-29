@echo off
setlocal
cd /d "%~dp0\..\.."
set "INPUT=data\output\latest_collection.json"
set "OUTPUT=data\output\accepted_jobs_review.csv"
if not exist "%INPUT%" (
  echo Hasil discovery belum tersedia.
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d = Get-Content '%INPUT%' -Raw | ConvertFrom-Json;" ^
  "$d.jobs | Select-Object title,company,location,posted_at,url,@{Name='Desc';Expression={($_.description | Out-String).Trim().Length}} | Export-Csv '%OUTPUT%' -NoTypeInformation -Encoding UTF8"
if errorlevel 1 (
  echo Gagal membuat CSV review.
  pause
  exit /b 1
)
echo CSV dibuat: %OUTPUT%
start "" "%CD%\%OUTPUT%"
pause
