$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$SettingsPath = Join-Path $ProjectRoot "config\settings.json"
$Settings = Get-Content $SettingsPath -Raw | ConvertFrom-Json
if (-not $Settings.scheduler.enabled) {
    Write-Host "scheduler.enabled masih false. Ubah menjadi true sebelum instalasi."
    exit 2
}
$Runner = Join-Path $ProjectRoot "scheduled_run.bat"
foreach ($time in $Settings.scheduler.run_times) {
    if ($time -notmatch '^([01]\d|2[0-3]):[0-5]\d$') {
        throw "Waktu tidak valid: $time"
    }
    $taskName = "KarirLog_" + $time.Replace(":", "")
    $action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$Runner`"" -WorkingDirectory $ProjectRoot
    $trigger = New-ScheduledTaskTrigger -Daily -At $time
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Description "KarirLog AI Agent V1.0 scheduled pipeline" -Force | Out-Null
    Write-Host "Task terpasang: $taskName pada $time WIB"
}
