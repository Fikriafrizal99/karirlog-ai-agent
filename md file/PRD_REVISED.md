# Product Requirements Document — KarirLog AI Agent V1.0

## 1. Produk

KarirLog AI Agent adalah aplikasi personal berbasis Python untuk mengumpulkan lowongan, menilai kecocokan, memilih CV yang telah tersedia, menyiapkan paket lamaran, membantu proses apply, dan menyimpan histori secara terstruktur.

## 2. Tujuan

- Mengurangi pekerjaan manual pencarian kerja.
- Memprioritaskan lowongan yang relevan.
- Mencegah apply pada lowongan yang tidak sesuai atau mencurigakan.
- Menghindari job dan application ganda.
- Menyiapkan Gmail draft dan portal prefill.
- Mempertahankan persetujuan manusia sebelum tindakan final.
- Menyimpan audit trail setiap tindakan.

## 3. Target pengguna

Satu pengguna pribadi. V1.0 tidak ditujukan sebagai SaaS, multi-user platform, atau layanan mass apply.

## 4. Pipeline final

```text
Load Configuration
→ Load Profile
→ Collect Jobs
→ Normalize
→ Deduplicate
→ AI/Rule Analysis
→ Decision Guardrail
→ Select and Validate CV
→ Build Application Package
→ Email Queue or Portal Queue
→ Gmail Draft / Portal Prefill
→ Explicit Approval / Manual Submit
→ Tracker and Audit
→ Telegram Report
```

## 5. Functional requirements

### FR-01 Job Discovery

Mengambil lowongan dari provider pencarian, RSS, URL langsung, dan CSV fallback.

### FR-02 Data quality

Melakukan normalisasi URL, metadata, dan fingerprint lintas sumber.

### FR-03 Analysis

Menghasilkan score, decision, seniority, requirement, skill gap, transferable strengths, dan red flag. AI harus memiliki fallback lokal.

### FR-04 Decision guardrail

Keputusan final dibatasi oleh hard requirement, seniority, pengalaman, excluded role, dan scam indicator.

### FR-05 CV selection

Memilih hanya dari CV yang sudah disiapkan pengguna. CV harus lolos validasi file dan tidak boleh diubah otomatis.

### FR-06 Application package

Menghasilkan subject, email body, cover letter, metadata, analysis, CV selection, attachment, dan checksum manifest.

### FR-07 Gmail draft

Membuat draft Gmail melalui OAuth Desktop dan Gmail API. Draft creation harus idempotent terhadap application status.

### FR-08 Email send approval

Pengiriman email hanya diperbolehkan bila:

1. Draft Gmail tersedia.
2. `send_mode` adalah `approved_send`.
3. Pengguna membuat approval code.
4. Approval code yang diberikan cocok.

### FR-09 Portal assistant

Membuka portal menggunakan browser profile terpisah, melakukan prefill field generik, mengunggah CV, menyimpan screenshot/report, dan berhenti sebelum submit.

### FR-10 Scheduler

Mendukung Windows Task Scheduler dengan satu atau beberapa jam harian. Scheduler tidak boleh mengirim email atau submit portal tanpa tindakan eksplisit pengguna.

### FR-11 Notification

Mengirim ringkasan pipeline dan delivery melalui Telegram bila diaktifkan.

### FR-12 Tracker dan audit

Menyimpan job, analysis, application, run, collector run, external Gmail ID, portal report, error, dan application event.

## 6. Non-functional requirements

- Modular dan dapat diuji tanpa kredensial live.
- SQLite migration kompatibel dengan baseline lama.
- Secret, OAuth token, CV, database, dan browser profile tidak masuk release.
- Kegagalan satu provider tidak menghentikan seluruh collector.
- Semua final actions mempunyai status yang dapat diaudit.

## 7. Safety requirements

- Tidak melewati CAPTCHA atau OTP.
- Tidak menyimpan plaintext approval code.
- Tidak mengirim email pada mode `draft_only`.
- Tidak submit portal otomatis.
- Tidak mengarang pengalaman atau skill.
- Tidak mengubah CV PDF.
- Tidak membuat application ganda untuk job yang sama.

## 8. Technology

- Python
- SQLite
- Requests dan BeautifulSoup
- OpenAI Responses API opsional
- Gmail API dan OAuth Desktop
- Playwright Chromium
- Telegram Bot API
- Windows Task Scheduler

## 9. Success criteria

- Collector dapat menghasilkan job terstruktur.
- Duplikat tidak menghasilkan analysis/application baru.
- Decision dan CV selection dapat dijelaskan.
- Gmail draft dapat dibuat dengan attachment.
- Email tanpa approval ditolak.
- Portal prefill berhenti sebelum submit.
- Scheduler dapat dipasang dari script.
- Audit trail mencatat seluruh delivery action.
- Semua automated tests lulus.

## 10. Out of scope

- Dashboard web.
- Mobile app.
- Multi-user.
- CAPTCHA bypass.
- Penyimpanan password portal.
- Auto-submit portal tanpa review.
- AI yang mengedit atau menambah pengalaman CV.
