# KarirLog Source Query V20

V18 menggabungkan sebelas jabatan exact dalam satu query untuk setiap sumber. Query masih berada di bawah batas karakter Brave, tetapi terlalu kompleks dan pada hasil live pengguna hanya mengembalikan satu kandidat dari dua belas request.

V20 menggunakan dua kelompok jabatan inti yang ringkas untuk masing-masing dari enam sumber:

1. Sales/marketing leadership.
2. Account/relationship/business development.

Perubahan:
- tetap hanya enam kelompok sumber yang dipilih pengguna;
- dua query ringkas per sumber, maksimal lima jabatan per query;
- menghapus tambahan operator generik yang tidak diperlukan;
- mode parameter `country_only` digunakan langsung agar tidak terjadi retry 422;
- rentang pencarian diperluas menjadi satu bulan, lalu quality gate tetap menolak data lama dan lowongan tertutup;
- halaman daftar portal boleh dibaca hanya untuk mengambil structured `JobPosting`; jika tidak ada detail terstruktur, halaman tetap ditolak;
- diagnostics mencatat jumlah hasil per sumber dan query yang benar-benar dijalankan;
- menu preview rencana pencarian memakai nol request Brave.
