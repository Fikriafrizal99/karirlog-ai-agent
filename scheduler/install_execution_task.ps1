param(
    [string]$Time = "08:00"
)

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$launcher = Join-Path $root "karirlog-execution\launcher\execute_latest.bat"
if (-not (Test-Path -LiteralPath $launcher)) { throw "Launcher Execution tidak ditemukan: $launcher" }

$parsed = [DateTime]::ParseExact($Time.Replace(":", ""), "HHmm", $null)
$taskName = "KARIRLOG_EXECUTION_{0:HHmm}" -f $parsed
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/d /c `"$launcher`""
$trigger = New-ScheduledTaskTrigger -Daily -At $parsed
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Description "KarirLog Execution analysis/package only; no email or portal submit" -Force | Out-Null
Write-Host "Registered $taskName -> $launcher"
