# karirlog-contracts

Shared `Job` dataclass and the versioned 15-column Search → Execution CSV
contract. This project has no runtime dependency outside Python.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pip install -r requirements-dev.txt
pytest tests -q
```

Keep this folder beside `karirlog-search` and `karirlog-execution`; both engines
install it with `pip install -e ..\karirlog-contracts`.
