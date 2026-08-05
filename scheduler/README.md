# Scheduler Windows

Install each task separately from PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scheduler\install_search_task.ps1 -Time 07:30
powershell -ExecutionPolicy Bypass -File .\scheduler\install_execution_task.ps1 -Time 08:00
```

Task names are `KARIRLOG_SEARCH_<HHMM>` and
`KARIRLOG_EXECUTION_<HHMM>`. The installers point to the active launcher under
each project, not a legacy `scheduled_run.bat`. Execution invokes analysis and
package preparation only; Gmail send and portal submit require explicit human
approval. `remove_tasks.ps1` removes only tasks with those KarirLog prefixes.
