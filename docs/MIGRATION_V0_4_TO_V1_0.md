# Migrasi V0.4 ke V1.0

1. Backup folder project V0.4.
2. Gunakan folder V1.0 sebagai project baru.
3. Salin file CV dari `documents/` lama ke `documents/` V1.0.
4. Salin nilai profile dan source config secara selektif.
5. Database lama boleh disalin ke `data/karirlog.db`; migration berjalan otomatis.
6. Jalankan `install_dependencies.bat`.
7. Jalankan `check_all.bat`.
8. Untuk portal, jalankan `install_browser.bat`.
9. Untuk Gmail, buat `credentials.json` dan isi email profile.

Kolom baru pada tabel applications:

- gmail_draft_id
- gmail_message_id
- approval_code_hash
- approved_at
- sent_at
- portal_report_path
- last_error

Tabel baru:

- application_events

V1.0 tidak mengirim email lama secara otomatis. Application V0.4 tetap berada pada queue draft sampai Gmail diaktifkan.
