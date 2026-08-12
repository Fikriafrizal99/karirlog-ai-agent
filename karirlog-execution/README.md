# karirlog-execution

KarirLog Execution adalah engine pemrosesan lamaran yang berdiri sendiri.

Execution hanya menerima file handoff CSV 15 kolom yang sudah direview manual,
lalu membantu sampai lamaran siap diteruskan: analisis, decision, CV selection,
application package, Gmail draft, portal assist, persistence, dan report Telegram.
Execution tidak mengimpor Search/discovery.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Salin `config/candidate_profile.example.json` menjadi
`config/candidate_profile.json`, lalu isi data pribadi dan simpan CV lokal seperti
sebelumnya. File profile pribadi tidak dikirim ke repository.

## Input wajib

Execution hanya membaca:

```text
data/input/discovery_latest.csv
```

File tersebut berasal dari hasil Search yang sudah direview manual di Excel.
Launcher tidak mengambil CSV langsung dari folder Search.

## Alur harian sederhana

Cukup jalankan:

```text
KARIRLOG_EXECUTION.bat
```

Launcher menjalankan Apply Assistant dengan urutan:

```text
discovery_latest.csv
        |
        v
analisis APPLY / REVIEW / SKIP
        |
        v
pilih CV + bangun package untuk APPLY
        |
        +--> EMAIL  -> buat Gmail draft otomatis
        |
        +--> PORTAL -> proses antrean dalam satu sesi browser
                         |
                         v
                  review / CAPTCHA / OTP / submit manual
```

Email tetap `draft_only`: KarirLog tidak mengirim email otomatis.
Portal tetap `manual_only`: KarirLog boleh membuka/prefill form, tetapi tombol
submit akhir tetap dikonfirmasi pengguna.

Jika session portal yang tersimpan masih valid, browser profile lama digunakan
kembali. Jika antrean portal kosong, portal assistant selesai tanpa membuka sesi
lamaran yang tidak diperlukan.

## Dua fokus Execution

`config/execution_focuses.json` menyelaraskan Execution dengan Search:

- `CORE_EXPERIENCE` untuk role yang paling dekat dengan pengalaman utama.
- `GENERAL_TRANSFERABLE` untuk operations, project/program, business,
  partnership, customer/client, dan process improvement yang masih memakai
  kemampuan transferable.

Fokus tersebut dioverlay ke `candidate_profile.json` hanya saat runtime. Data
pribadi tetap berasal dari file lokal dan temporary active profile dihapus setelah
run selesai.

CV selector diarahkan seperti berikut:

- Core Experience -> `CV Sales Management`.
- General Transferable -> `CV General`.

## Override per run

Kalau suatu saat hanya ingin analisis tanpa salah satu delivery helper:

```powershell
python apply_assistant.py --skip-gmail
python apply_assistant.py --skip-portal
```

Command granular lama tetap tersedia untuk troubleshooting:

```powershell
python main.py execute
python main.py create-gmail-drafts
python main.py assist-portal-queue
python main.py check-cv
python main.py check-gmail
python main.py list-applications
```

## Testing

```powershell
pytest tests -q
```
