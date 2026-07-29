# Modul 2 — Live Job Collector

## Tujuan

Mengubah KarirLog dari pipeline berbasis file contoh menjadi pipeline yang mampu mengumpulkan lowongan aktual melalui beberapa sumber dengan kontrak data yang sama.

## Keputusan Arsitektur

### Adapter per sumber

Setiap sumber diimplementasikan sebagai adapter mandiri yang menghasilkan objek `Job`. Pipeline tidak mengetahui detail API, RSS, atau HTML sumber.

### Provider search terpisah dari parser halaman

Search provider digunakan untuk menemukan URL. Detail lowongan diambil dari metadata `JobPosting` jika tersedia. Dengan pola ini, provider search dapat diganti tanpa mengubah analysis engine.

### Tidak scraping portal secara keras

V0.2 tidak menyimpan selector khusus JobStreet, Glints, atau portal lain. Selector portal sangat mudah berubah dan login/CAPTCHA dapat menimbulkan kegagalan. Dukungan browser-assisted disiapkan pada modul tersendiri.

### Failure isolation

Kegagalan satu collector tidak menghentikan collector lain. Status setiap sumber disimpan sebagai:

- `SUCCESS`
- `SKIPPED`
- `FAILED`

### Safe fallback

Mode `live_with_fallback` hanya memakai CSV bila seluruh sumber live menghasilkan nol lowongan.

## Kontrak Job

Setiap collector menghasilkan:

- title
- company
- location
- url
- description
- source
- apply_email
- posted_at
- source_job_id
- employment_type
- salary
- remote
- fingerprint

## Collector

### Brave Web Search

- Query otomatis dari target role dan lokasi.
- Freshness configurable.
- Domain allowlist dan exclusion.
- Hydrate halaman hasil untuk membaca JSON-LD.
- Search snippet menjadi fallback bila JSON-LD tidak ditemukan.

### URL List

- Membaca `data/input/job_urls.txt`.
- Cocok untuk URL dari Telegram, LinkedIn, WhatsApp, browser, atau portal.
- Mendukung strict metadata dan generic page fallback.

### RSS/Atom

- Membaca feed publik dengan parser XML standard library.
- Dapat membuka halaman entry untuk metadata lebih lengkap.

### CSV

- Mode sample.
- Import data manual.
- Fallback saat hasil live kosong.

## Deduplikasi

Fingerprint utama dibentuk dari normalisasi:

```text
title + company + location
```

Tujuannya agar satu lowongan yang ditemukan melalui Brave, RSS, dan URL list hanya diproses satu kali. Bila title/company tidak tersedia, source ID atau canonical URL digunakan.

## Database Changes

Kolom baru pada `jobs`:

- source_job_id
- employment_type
- salary
- remote

Kolom baru pada `runs`:

- raw_found
- cross_source_duplicates
- fallback_used

Tabel baru:

```text
collector_runs
```

Migrasi ringan otomatis ditambahkan agar database V0.1 tetap dapat dibuka.

## Guardrail

- Request memiliki timeout.
- Retry untuk 429 dan error server.
- User agent jelas.
- Apply tetap draft-only.
- Source dengan key kosong ditandai SKIPPED.
- Kesalahan fetch satu URL tidak mematikan URL lain.
- Domain sosial tertentu dikecualikan secara default.
