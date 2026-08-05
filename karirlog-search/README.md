# karirlog-search

Independent discovery engine. It owns Brave Search, RSS, URL, and CSV
collectors and writes only the shared 15-column CSV handoff; it does not import
Execution modules.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`requirements.txt` installs the sibling contracts package editable. Copy
`.env.example` to `.env` and set `BRAVE_SEARCH_API_KEY` for live mode. Search
still works without that key through CSV fallback.

## Commands

```powershell
python main.py collect --mode sample
python main.py collect
python main.py collect --mode live
python main.py check-sources
```

`sample` reads `data/input/jobs_sample.csv`; live fallback reads
`data/input/Job_List.csv` when Brave is unavailable. Relative config paths are
resolved from this project root, so commands work from another folder. Outputs
are `data/output/discovery_latest.csv`, timestamped CSV, and diagnostics.

Run tests with `pytest tests -q`. Use the Windows launchers under `launcher/`;
they select the project `.venv` and never depend on current working directory.
