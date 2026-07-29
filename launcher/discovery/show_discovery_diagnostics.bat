@echo off
setlocal
cd /d "%~dp0\..\.."
set "FILE=data\output\latest_discovery_diagnostics.json"
if not exist "%FILE%" (
  echo Diagnostics belum tersedia.
  echo Jalankan discovery terlebih dahulu.
  pause
  exit /b 2
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d = Get-Content '%FILE%' -Raw | ConvertFrom-Json;" ^
  "Write-Host ''; Write-Host '=== DISCOVERY DIAGNOSTICS ===';" ^
  "Write-Host ('Diterima : ' + $d.accepted_count);" ^
  "Write-Host ('API baru : ' + $d.search.api_calls);" ^
  "Write-Host ('Negara   : ' + (($d.search.response_countries.PSObject.Properties | ForEach-Object { $_.Name + '=' + $_.Value }) -join ', '));" ^
  "Write-Host ('Sumber   : ' + (($d.accepted_by_source.PSObject.Properties | ForEach-Object { $_.Name + '=' + $_.Value }) -join ', '));" ^
  "Write-Host ''; Write-Host 'LOWONGAN DITERIMA';" ^
  "$d.accepted | Select-Object source,title,company,location,posted_at,url | Format-List;" ^
  "Write-Host 'RINGKASAN DITAHAN';" ^
  "$d.filter_counts.PSObject.Properties | Sort-Object Value -Descending | Format-Table Name,Value -AutoSize;" ^
  "Write-Host ('File lengkap: %FILE%')"
pause
