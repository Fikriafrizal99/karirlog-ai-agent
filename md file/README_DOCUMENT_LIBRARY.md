# KarirLog Document Library V1.1

Setiap profile memakai nama subfolder yang sama pada tiga lokasi:

```text
documents/cv/{profile_id}/
documents/attachments/{profile_id}/
documents/supporting_documents/{profile_id}/
```

Aturan:

- `cv`: tepat satu CV aktif per profile.
- `attachments`: seluruh file valid otomatis ikut ke paket dan Gmail draft.
- `supporting_documents`: hanya ikut bila deskripsi lowongan secara eksplisit meminta tipe dokumen tersebut.
- Dokumen sensitif seperti KTP, KK, NPWP, paspor, rekening, dan dokumen medis tidak pernah dikirim otomatis.
