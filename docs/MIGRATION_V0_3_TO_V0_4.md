# Migration V0.3 → V0.4

## Langkah

1. Backup folder V0.3 dan `data/karirlog.db`.
2. Gunakan source V0.4.
3. Salin database lama ke `data/karirlog.db` bila ingin mempertahankan histori.
4. Salin CV ke folder `documents/`.
5. Sesuaikan `config/cv_library.json`.
6. Jalankan `check_cv.bat`.
7. Jalankan pipeline.

## Migrasi database

Saat aplikasi dimulai, kolom V0.4 ditambahkan otomatis:

- `applications.selected_cv_id`
- `applications.selected_cv_path`
- `applications.cv_selection_status`
- `applications.cv_selection_score`
- `applications.apply_channel`
- `applications.recipient`
- `applications.manifest_path`
- `applications.updated_at`
- Statistik application readiness pada tabel `runs`

## Draft lama

Application berstatus `DRAFT_READY` dari V0.1–V0.3 dianggap paket legacy. Saat lowongan muncul kembali, paket dibangun ulang ke format V0.4 memakai analysis yang sudah ada.

## Rollback

Database yang sudah ditambah kolom tetap dapat dibaca oleh SQLite. Namun, untuk rollback source code secara bersih, gunakan backup database V0.3.
