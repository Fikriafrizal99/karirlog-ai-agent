# Module 8 — Document & Attachment Library V1.1

## Struktur

```text
documents/
├── cv/{profile_id}/
├── attachments/{profile_id}/
└── supporting_documents/{profile_id}/
```

Nama `{profile_id}` harus sama pada ketiga folder. Contoh `sap_abap`.

## Perilaku

1. CV selector memilih profile berdasarkan role, skill, priority, dan exclusion.
2. Folder `cv/{profile_id}` wajib berisi tepat satu CV valid.
3. Semua file valid dalam `attachments/{profile_id}` ikut otomatis.
4. File dalam `supporting_documents/{profile_id}` hanya ikut bila lowongan secara eksplisit meminta tipe dokumen tersebut.
5. File sensitif tidak pernah dikirim otomatis.
6. Semua file dideduplikasi dengan SHA-256.
7. Package manifest menyimpan urutan attachment; Gmail selalu memasang CV pertama.

## Status baru

- `REVIEW_MULTIPLE_CV`
- `REVIEW_DOCUMENT`
- `REVIEW_ATTACHMENT_SIZE`
- `BLOCKED_INVALID_FILE`
- `MANUAL_APPROVAL_REQUIRED` pada file sensitif

## Validasi

```text
check_documents.bat
check_cv.bat
```
