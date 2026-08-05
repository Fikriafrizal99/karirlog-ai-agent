# KarirLog — separated engines

KarirLog dipisahkan menjadi tiga project independen:

```text
karirlog-contracts/   Job model + kontrak CSV 15 kolom
karirlog-search/      discovery sample, CSV fallback, Brave/RSS/URL collector
karirlog-execution/   analysis, SQLite, CV/document selection, package + delivery prep
integration-tests/    test handoff Search → Execution
```

## Instalasi

Gunakan Python 3.11+ dan virtual environment terpisah untuk setiap engine.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Kedua engine mengonsumsi contracts sebagai local editable dependency:

```powershell
python -m pip install -e ..\karirlog-contracts
```

`requirements.txt` masing-masing sudah memuat baris editable tersebut ketika
ketiga folder diletakkan berdampingan.

## Search Engine

Edit `karirlog-search/config/search_profile.json` dan `config/sources.json`.
Salin `.env.example` menjadi `.env`, lalu isi `BRAVE_SEARCH_API_KEY` untuk live
search. Tanpa key, mode default `live_with_fallback` tetap berjalan memakai
`data/input/Job_List.csv`.

```powershell
python karirlog-search/main.py collect --mode sample
python karirlog-search/main.py collect
python karirlog-search/main.py check-sources
```

Handoff ditulis sebagai UTF-8-SIG dengan tepat 15 kolom ke
`karirlog-search/data/output/discovery_latest.csv` dan CSV timestamped.

## Execution Engine

Salin `config/candidate_profile.example.json` menjadi
`config/candidate_profile.json`, sesuaikan profil, lalu daftarkan CV di
`config/cv_library.json`. Jika CV belum tersedia, engine menghasilkan status
`BLOCKED_CV_MISSING` dan pesan setup; CV pribadi tidak disimpan di repository.

```powershell
python karirlog-execution/main.py execute `
  --input karirlog-search/data/output/discovery_latest.csv `
  --analysis-mode rule_only
python karirlog-execution/main.py execute --analysis-mode ai_with_fallback
python karirlog-execution/main.py check-cv
python karirlog-execution/main.py check-documents
python karirlog-execution/main.py check-gmail
python karirlog-execution/main.py list-applications
```

AI mode menggunakan `OPENAI_API_KEY`; `rule_only` tidak membutuhkan Brave atau
OpenAI key. Gmail membutuhkan `credentials.example.json` yang disalin menjadi
`credentials.json`, OAuth token lokal, dan dependency Google API. Playwright
dibutuhkan hanya untuk portal assistant. Tidak ada command scheduled yang
mengirim email atau submit portal tanpa approval eksplisit.

Database default adalah `karirlog-execution/data/database/karirlog.db` dan dibuat
otomatis saat execution pertama. Output aplikasi berada di
`karirlog-execution/data/output/`.

## Anti-proses ulang dan lifecycle

Job yang sudah `APPLIED`, `SKIPPED`, atau `EXPIRED` terminal. Job `REVIEW`,
`BLOCKED_CV_MISSING`, dan package final tidak diulang pada run berikutnya.
Fingerprint analisis/package disimpan untuk mendeteksi perubahan konfigurasi
atau CV. Gunakan override secara eksplisit hanya untuk run aktif:

```powershell
python karirlog-execution/main.py execute --force-reprocess
python karirlog-execution/main.py execute --rebuild-packages
```

`--force-reprocess` mengulang analisis; `--rebuild-packages` mengizinkan rebuild
package. Keduanya tidak menjadi default.

## Tests dan launcher Windows

```powershell
pytest karirlog-contracts/tests -q
pytest karirlog-search/tests -q
pytest karirlog-execution/tests -q
pytest integration-tests -q
python -m compileall karirlog-contracts/src karirlog-search/src karirlog-execution/src
```

Dari root gunakan `KARIRLOG_SEARCH.bat` atau `KARIRLOG_EXECUTION.bat`.
Launcher rinci ada di folder `launcher/` masing-masing dan selalu menentukan
root dari lokasi file BAT, sehingga tidak bergantung pada current working
directory. Scheduler PowerShell terpisah ada di `scheduler/`; installer hanya
menunjuk ke launcher aktif dan execution scheduler tidak mengirim email.

Monolit lama tetap berada di luar folder hasil pemisahan sampai final
verification selesai.
