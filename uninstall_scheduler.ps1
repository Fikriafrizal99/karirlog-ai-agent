$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Settings = Get-Content (Join-Path $ProjectRoot "config\settings.json") -Raw | ConvertFrom-Json
foreach ($time in $Settings.scheduler.run_times) {
    $taskName = "KarirLog_" + $time.Replace(":", "")
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Task dihapus: $taskName"
}
