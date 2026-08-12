# karirlog-search

KarirLog Search adalah engine discovery yang berdiri sendiri.

Tujuannya sederhana:

```text
Brave Search
  -> validasi dasar
  -> deduplikasi
  -> discovery_latest.csv
  -> report + CSV ke Telegram
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

Agar hasil Search dikirim ke Telegram, isi juga:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Secara default `telegram_enabled` dan `telegram_send_csv` aktif pada
`config/search_settings.json`. Jika token/chat ID belum diisi, Search tetap
selesai normal dan CSV tetap tersimpan; hanya pengiriman Telegram yang dilewati.

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

## Report Telegram

Setelah Search selesai, Telegram menerima dua kiriman:

1. Ringkasan Search: data mentah, lowongan unik, duplikat, fallback, dan status collector.
2. File `discovery_latest.csv` sebagai document attachment.

Telegram hanya berfungsi sebagai report/distribusi file. Search tidak pernah
menjalankan Execution otomatis dan tidak menyalin CSV langsung ke folder
Execution.

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
2. Ambil `discovery_latest.csv` dari Telegram atau buka file lokal di `data/output/`.
3. Review dan hapus baris yang tidak ingin diteruskan di Excel.
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
