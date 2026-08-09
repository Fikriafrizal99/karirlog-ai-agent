# karirlog-search

KarirLog Search adalah engine discovery yang berdiri sendiri.

Tujuannya sederhana:

```text
Brave Search
  -> validasi dasar
  -> deduplikasi
  -> discovery_latest.csv
  -> review manual di Excel
```

Search tidak mengimpor AI analysis, CV, database, Gmail, portal assistant, atau
modul Execution.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Salin `.env.example` menjadi `.env`, lalu isi `BRAVE_SEARCH_API_KEY` untuk live
search. Jika key tidak tersedia, mode `live_with_fallback` dapat memakai CSV
fallback.

## Menjalankan Search

Paling sederhana:

```text
KARIRLOG_SEARCH.bat
```

Atau:

```powershell
python main.py collect
python main.py check-sources
python main.py show-plan
```

Output utama:

```text
data/output/discovery_latest.csv
```

Search juga menyimpan arsip timestamped dan diagnostics.

## Coverage pencarian

Query planner memakai seluruh `target_roles` pada `config/search_profile.json`.
Role dibagi ke beberapa query dan diputar ke sumber yang dipilih agar semua
target role mendapat coverage tanpa membuat kombinasi role x source yang
berlebihan.

`preferred_locations` juga dimasukkan langsung ke query. Nilai `Indonesia`
dipakai sebagai konteks negara, bukan sebagai alternatif lokasi di dalam OR
clause, sehingga kota/area pilihan tidak kehilangan prioritas.

## Handoff ke Execution

Handoff sengaja manual:

1. Jalankan Search.
2. Buka `data/output/discovery_latest.csv` di Excel.
3. Review dan hapus baris yang tidak ingin diteruskan.
4. Simpan/copy file hasil review ke:

```text
../karirlog-execution/data/input/discovery_latest.csv
```

5. Jalankan `KARIRLOG_EXECUTION.bat`.

Search tidak menyalin CSV ke Execution otomatis.

## Testing

```powershell
pytest tests -q
```
