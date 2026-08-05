# karirlog-execution

Independent execution engine. It accepts only the 15-column CSV handoff,
performs rule/AI analysis, persists jobs/analyses/applications in SQLite,
selects CV and supporting documents, and creates guarded application packages.
It does not import Search or discovery modules.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy `config/candidate_profile.example.json` to
`config/candidate_profile.json`, then configure `config/cv_library.json` with
local CV paths. Keep the active profile, real CVs, credentials, OAuth token,
browser profile, and database local; they are ignored by git.

Gmail setup uses `credentials.example.json` → `credentials.json` and OAuth on
the first Gmail command. Portal setup uses Playwright or an external Chrome CDP
session. Both delivery paths remain approval/manual-only; execution does not
send an email or submit a portal during analysis.

## Commands

```powershell
python main.py execute --input ..\karirlog-search\data\output\discovery_latest.csv --analysis-mode rule_only
python main.py execute --analysis-mode ai_with_fallback
python main.py check-ai
python main.py check-cv
python main.py check-documents
python main.py check-gmail
python main.py list
python main.py list-applications
```

The default database is created automatically under `data/database/`; reports
and packages are written under `data/output/`. A missing CV produces a clear
`BLOCKED_CV_MISSING` package and does not retry on every run. Use
`--force-reprocess` for one explicit analysis rerun and `--rebuild-packages` for
one explicit package rebuild.

Run `pytest tests -q`. The minimal E2E test uses only a repository fixture PDF,
never a personal CV.
