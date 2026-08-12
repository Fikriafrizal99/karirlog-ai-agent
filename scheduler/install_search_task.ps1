param(
    [string]$Time = "07:30"
)

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$launcher = Join-Path $root "karirlog-search\launcher\collect_live.bat"
if (-not (Test-Path -LiteralPath $launcher)) { throw "Launcher Search tidak ditemukan: $launcher" }

$parsed = [DateTime]::ParseExact($Time.Replace(":", ""), "HHmm", $null)
$taskName = "KARIRLOG_SEARCH_{0:HHmm}" -f $parsed
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/d /c `"$launcher`""
$trigger = New-ScheduledTaskTrigger -Daily -At $parsed
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Description "KarirLog Search discovery; Brave/cache/CSV only" -Force | Out-Null
Write-Host "Registered $taskName -> $launcher"
