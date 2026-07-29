# KarirLog Clean Keep Submitted V19

Menambahkan pembersihan aman melalui Control Panel.

Dipertahankan:
- aplikasi berstatus `PORTAL_SUBMITTED`
- aplikasi berstatus `EMAIL_SENT`
- job dan analisis terkait aplikasi tersebut
- paket output yang dirujuk aplikasi submitted
- profil browser/login, CV, config, `.env`, dan token Gmail

Dihapus:
- draft, review, gagal, dan aplikasi yang belum terkirim
- job serta analisis yang tidak terkait submitted
- histori run/collector
- hasil discovery dan output non-submit
- cache discovery

Sebelum pembersihan, database dibackup otomatis ke `data/backups/keep_submitted_<timestamp>`.
