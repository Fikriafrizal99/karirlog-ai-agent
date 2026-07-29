# KarirLog AI Agent V1.0

KarirLog AI Agent adalah aplikasi Python untuk penggunaan pribadi yang menghubungkan seluruh proses pencarian kerja dalam satu pipeline:

```text
Job Collector
  → Normalisasi dan deduplikasi
  → AI/rule analysis
  → Decision guardrail
  → CV selector
  → Application package
  → Gmail draft atau Portal Assistant
  → Approval/manual submit
  → Tracker, audit trail, Telegram, scheduler
```

## Status V1.0

Seluruh modul utama sudah terintegrasi. Sistem dapat berjalan tanpa API AI atau Gmail karena masing-masing integrasi mempunyai fallback/status yang jelas.

Pengamanan default:

- Gmail hanya membuat draft.
- Pengiriman email membutuhkan dua langkah dan kode approval per lamaran.
- Portal Assistant melakukan prefill, tetapi tidak menekan tombol submit.
- CAPTCHA, OTP, pertanyaan khusus perusahaan, dan persetujuan legal tetap diselesaikan pengguna.
- Isi CV tidak diubah otomatis.
- CV, OAuth token, database, dan browser profile tidak dimasukkan ke Git/ZIP release.

## Modul

1. Configuration dan user profile.
2. Live Job Collector.
3. AI Job Analysis dengan rule fallback.
4. CV Selector dan Application Builder.
5. Gmail Draft dan Approved Send.
6. Portal Apply Assistant.
7. Scheduler, Telegram, tracker, dan audit trail.

## Instalasi Windows

Jalankan:

```text
install_dependencies.bat
install_browser.bat
```

`install_browser.bat` dibutuhkan hanya untuk Portal Assistant.

## Konfigurasi awal

### 1. Profil

Isi `config/profil.json`:

- `full_name`
- `email`
- `phone`
- target role
- lokasi
- skill
- pengalaman yang benar-benar dimiliki

### 2. CV

Masukkan file sesuai `config/cv_library.json`, minimal:

```text
documents/CV_SAP_ABAP.pdf
documents/CV_General.pdf
```

Validasi:

```text
check_cv.bat
```

KarirLog hanya memilih dan melampirkan CV. Sistem tidak mengedit isi PDF.

### 3. Environment

Salin `.env.example` menjadi `.env`, lalu isi yang digunakan:

```text
BRAVE_SEARCH_API_KEY=
OPENAI_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Semua key bersifat opsional. Tanpa key pencarian, mode `live_with_fallback` memakai CSV fallback. Tanpa key AI, analisis lokal digunakan.

## Menjalankan pipeline

### Tes dengan data sample

```text
run_sample.bat
```

### Live collector

```text
run_live.bat
```

### Pipeline terintegrasi termasuk Gmail draft

```text
scheduled_run.bat
```

Gmail draft hanya dibuat jika `gmail.enabled` bernilai `true`.

## Setup Gmail

1. Buat OAuth Client untuk aplikasi Desktop pada Google Cloud.
2. Aktifkan Gmail API.
3. Unduh file OAuth dan simpan sebagai `credentials.json` di root project.
4. Isi email pengirim pada `config/profil.json`.
5. Ubah konfigurasi:

```json
"gmail": {
  "enabled": true,
  "credentials_path": "credentials.json",
  "token_path": "data/secrets/gmail_token.json",
  "send_mode": "draft_only",
  "auto_create_drafts": true,
  "max_drafts_per_run": 10,
  "max_sends_per_day": 5,
  "approval_ttl_minutes": 30
}
```

Cek:

```text
python -m karirlog.cli check-gmail
```

Run pertama akan membuka OAuth consent browser. Token disimpan lokal di `data/secrets/`.

## Alur email yang aman

### A. Buat Gmail draft

```text
create_gmail_drafts.bat
```

Status berubah:

```text
DRAFT_READY_EMAIL → GMAIL_DRAFT_CREATED
```

### B. Periksa draft di Gmail

Periksa penerima, subject, isi, dan CV.

### C. Izinkan approved send

Ubah `gmail.send_mode` menjadi:

```json
"approved_send"
```

Buat kode approval:

```text
approve_email.bat APPLICATION_ID
```

Status:

```text
GMAIL_DRAFT_CREATED → EMAIL_APPROVAL_PENDING
```

Kirim menggunakan kode yang baru dibuat:

```text
send_email.bat APPLICATION_ID KODE_APPROVAL
```

Status akhir:

```text
EMAIL_SENT
```

Kode approval hanya berlaku untuk satu application, kedaluwarsa setelah 30 menit secara default, dan plaintext-nya tidak disimpan di database. Batas default pengiriman adalah lima email per hari.

## Alur portal

Lihat ID application:

```text
list_applications.bat
```

Buka Portal Assistant:

```text
assist_portal.bat APPLICATION_ID
```

KarirLog akan:

- Membuka portal pada browser profile khusus.
- Mengisi nama, email, telepon jika field dikenali.
- Mengunggah CV jika input file ditemukan.
- Mengisi cover letter jika field dikenali.
- Mengambil screenshot sebelum submit.
- Tidak menekan tombol submit.

Setelah kamu memeriksa dan submit manual:

```text
mark_portal_submitted.bat APPLICATION_ID
```

Status akhir:

```text
PORTAL_SUBMITTED
```

## Scheduler Windows

Atur `config/settings.json`:

```json
"scheduler": {
  "enabled": true,
  "timezone": "Asia/Jakarta",
  "run_times": ["07:30"],
  "create_gmail_drafts": true
}
```

Kemudian jalankan PowerShell sebagai user yang sama:

```powershell
powershell -ExecutionPolicy Bypass -File .\install_scheduler.ps1
```

Hapus scheduler:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_scheduler.ps1
```

Scheduler menjalankan collector, analisis, application builder, tracker, Telegram, lalu membuat Gmail draft. Scheduler tidak mengirim email dan tidak submit portal.

## Telegram

Isi token/chat ID di `.env`, lalu ubah:

```json
"telegram_enabled": true
```

Telegram menerima ringkasan pipeline dan delivery update. Telegram tidak digunakan untuk mengirim lamaran.

## Tracker dan audit

```text
list_applications.bat
list_audit.bat
```

Status utama:

- `DRAFT_READY_EMAIL`
- `GMAIL_DRAFT_CREATED`
- `EMAIL_APPROVAL_PENDING`
- `EMAIL_SENT`
- `DRAFT_READY_PORTAL`
- `PORTAL_REVIEW_REQUIRED`
- `PORTAL_SUBMITTED`
- `REVIEW_CV`
- `BLOCKED_CV_MISSING`
- `BLOCKED_DESTINATION`
- `INVALIDATED_BY_REANALYSIS`

## Testing

```text
set PYTHONPATH=src
python -m unittest discover -s tests -v
```

V1.0 memiliki 28 automated tests untuk collector, parsing, AI fallback, decision guardrail, CV selection, package builder, migration, Gmail MIME/draft/send approval, portal workflow, scheduler, deduplikasi, dan reanalysis.

## Batasan V1.0

- Portal lowongan berbeda-beda, sehingga prefill generik tidak selalu mengenali semua field.
- CAPTCHA, OTP, login, dan pertanyaan tambahan harus ditangani manual.
- Sistem tidak boleh digunakan untuk spam atau mass apply tanpa review.
- Gmail dan provider pencarian memerlukan kredensial milik pengguna sendiri.
- Live AI, Gmail, dan portal nyata hanya bisa diuji setelah kredensial pengguna tersedia.
