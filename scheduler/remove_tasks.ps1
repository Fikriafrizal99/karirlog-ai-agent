Get-ScheduledTask -TaskName "KARIRLOG_SEARCH_*" -ErrorAction SilentlyContinue |
    ForEach-Object { Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false }
Get-ScheduledTask -TaskName "KARIRLOG_EXECUTION_*" -ErrorAction SilentlyContinue |
    ForEach-Object { Unregister-ScheduledTask -TaskName $_.TaskName -Confirm:$false }
Write-Host "KarirLog Search/Execution scheduled tasks removed."
