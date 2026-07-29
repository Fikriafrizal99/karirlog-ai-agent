# Migration V1.0 → V1.1

1. Ekstrak Upgrade Patch V1.1 ke root project V1.0 dan izinkan overwrite source.
2. Jalankan `upgrade_to_v1_1_documents.bat`.
3. Script membuat backup konfigurasi di `data/upgrade_backup/`.
4. CV lama disalin ke `documents/cv/{profile_id}/` tanpa menghapus file lama.
5. Masukkan portfolio/sertifikat otomatis ke `documents/attachments/{profile_id}/`.
6. Masukkan ijazah/transkrip ke `documents/supporting_documents/{profile_id}/`.
7. Jalankan `check_documents.bat`, `check_cv.bat`, lalu pipeline.

Migration tidak menghapus atau mengganti `profile.json`, `.env`, `credentials.json`, token OAuth, database, output, maupun browser profile.
