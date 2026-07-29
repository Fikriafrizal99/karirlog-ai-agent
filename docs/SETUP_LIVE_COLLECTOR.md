# Setup Live Collector — Windows

## A. Uji Baseline Tanpa API Key

1. Extract ZIP.
2. Jalankan `check_sources.bat`.
3. Jalankan `run_sample.bat`.
4. Pastikan terlihat 4 lowongan contoh dan 2 status APPLY.

## B. Mengaktifkan Web Search

1. Buat API key Brave Search.
2. Duplikasi `.env.example` dan rename menjadi `.env`.
3. Isi `BRAVE_SEARCH_API_KEY`.
4. Jalankan `check_sources.bat`.
5. Jalankan `collect_live.bat`.
6. Buka `data/output/latest_collection.json`.
7. Bila hasil sudah relevan, jalankan `run_live.bat`.

## C. Menyesuaikan Target

Edit `config/profil.json`:

```json
"target_roles": [
  "Junior SAP ABAP Developer",
  "SAP ABAP Consultant",
  "SAP Technical Consultant"
]
```

Edit lokasi:

```json
"preferred_locations": [
  "Jakarta",
  "Jabodetabek",
  "Bandung",
  "Remote",
  "Indonesia"
]
```

## D. Custom Query

Tambahkan `queries` pada collector Brave di `config/sources.json`:

```json
"queries": [
  "SAP ABAP junior lowongan Indonesia",
  "SAP technical consultant remote Indonesia",
  "ABAP developer Jakarta vacancy"
]
```

Saat `queries` tersedia, query otomatis dari profile tidak digunakan.

## E. Membatasi Portal

Allowlist:

```json
"allowed_domains": [
  "jobstreet.co.id",
  "glints.com",
  "linkedin.com",
  "kalibrr.com"
]
```

Kosongkan allowlist untuk mengizinkan seluruh domain selain exclusion.

## F. Troubleshooting

### `NEEDS_KEY`

File `.env` belum dibuat atau API key kosong.

### Collector `FAILED`

Periksa koneksi, API key, limit provider, atau format feed.

### Live result 0

- Perluas target role.
- Hapus freshness sementara dengan `"freshness": ""`.
- Tambah custom query.
- Tambah URL manual.
- Jalankan `live_with_fallback` untuk memastikan pipeline lain tetap teruji.

### Hasil tidak relevan

- Tambah negative keyword pada `query_suffix`.
- Isi `allowed_domains`.
- Perketat target role.
- Review output collection sebelum pipeline penuh.
