# Release Notes — KarirLog AI Agent V1.1

## Added

- Profile-based Document & Attachment Library.
- Tiga folder berpasangan per `profile_id`: `cv`, `attachments`, dan `supporting_documents`.
- Pemilihan tepat satu CV per profile; lebih dari satu CV menghasilkan `REVIEW_MULTIPLE_CV`.
- Attachment profile otomatis disalin ke application package dan Gmail draft.
- Supporting document hanya dipilih saat lowongan secara eksplisit meminta tipe dokumen terkait.
- Dokumen sensitif ditahan dengan status `MANUAL_APPROVAL_REQUIRED`.
- Deduplikasi file berdasarkan SHA-256.
- `document_selection.json` dan manifest attachment berurutan.
- Gmail melampirkan seluruh file dari manifest dengan CV selalu pada urutan pertama.
- Portal Assistant membaca seluruh attachment; upload semua hanya jika input portal mendukung multiple file.
- `check_documents.bat` dan migrasi aman `upgrade_to_v1_1_documents.bat`.

## Compatibility

- Konfigurasi lama yang memakai field `path` tetap didukung.
- Database V1.0 tidak perlu di-reset.
- Gmail OAuth, token, profile, `.env`, database, dan histori tidak diubah oleh migration script.

## Tests

- 28 test V1.0 tetap lulus.
- 5 test baru Document Library lulus.
- Total: 33 automated tests.
