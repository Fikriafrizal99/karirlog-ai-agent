# Module 4 — CV Selector & Application Builder

## Tujuan

Menghubungkan keputusan APPLY dengan CV yang sudah dimiliki pengguna dan menghasilkan paket lamaran yang aman untuk tahap pengiriman berikutnya.

## Komponen

### `cv_selector.py`

- Membaca CV library.
- Menjaga kompatibilitas dengan `profile.cv_files` versi lama.
- Memvalidasi file.
- Menghitung skor kecocokan.
- Menghasilkan status READY, REVIEW, atau BLOCKED.

### `application_builder.py`

- Menentukan channel email atau portal.
- Membuat cover letter dan email lokal.
- Menyalin CV terpilih.
- Menghapus paket generasi lama sebelum rebuild agar lampiran stale tidak tertinggal.
- Membuat application metadata dan manifest checksum.

### `database.py`

Menyimpan:

- Selected CV ID dan path.
- CV selection status dan score.
- Apply channel dan recipient.
- Manifest path.
- Waktu update paket.

### `pipeline.py`

- Memanggil selector hanya untuk decision yang ada di `build_application_for`.
- Menghitung ready/review/blocked.
- Rebuild paket incomplete tanpa reanalysis.
- Menjaga satu application record per job.

## Scoring Ringkas

```text
Role keyword pada title      → bobot utama
Role keyword pada context    → bobot pendukung
Skill keyword cocok          → bobot tambahan
Priority CV                  → tie breaker kecil
Fallback general             → skor minimum rendah
Excluded role                → penalti besar
```

## Safety

- Selector tidak membaca dan tidak mengubah isi CV.
- Tidak ada klaim pengalaman baru yang dibuat.
- Cover letter hanya memakai profile summary, matched skill, dan transferable strength.
- CV ambigu ditahan untuk review.
- Tidak ada pengiriman pada V0.4.
