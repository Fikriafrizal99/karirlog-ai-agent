# karirlog-execution

KarirLog Execution adalah engine pemrosesan lamaran yang berdiri sendiri.

Execution hanya menerima file handoff CSV 15 kolom, lalu menjalankan analisis,
decision, CV selection, application package, persistence, serta delivery prep.
Execution tidak mengimpor Search/discovery.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Salin `config/candidate_profile.example.json` menjadi
`config/candidate_profile.json`, lalu konfigurasi CV lokal.

## Input wajib

Execution hanya membaca:

```text
data/input/discovery_latest.csv
```

File tersebut harus berasal dari hasil Search yang sudah kamu review manual di
Excel. Launcher tidak lagi mengambil CSV langsung dari folder `karirlog-search`.

Alur:

```text
karirlog-search/data/output/discovery_latest.csv
              |
              v
        review di Excel
              |
              v
karirlog-execution/data/input/discovery_latest.csv
              |
              v
        Execution Engine
```

## Menjalankan

Paling sederhana:

```text
KARIRLOG_EXECUTION.bat
```

Atau:

```powershell
python main.py execute
python main.py execute --analysis-mode ai_with_fallback
python main.py check-ai
python main.py check-cv
python main.py check-documents
python main.py check-gmail
python main.py list
python main.py list-applications
```

Default `config/execution_settings.json` sudah menunjuk ke
`data/input/discovery_latest.csv`.

Gmail dan portal tetap guarded/manual. Analisis tidak mengirim email dan tidak
menekan submit portal secara otomatis.

## Testing

```powershell
pytest tests -q
```
