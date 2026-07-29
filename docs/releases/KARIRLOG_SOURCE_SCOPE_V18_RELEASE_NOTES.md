# KarirLog Source Scope V18

Discovery dibatasi menjadi enam kelompok sumber:

1. KitaLulus
2. Jobstreet
3. LinkedIn Jobs
4. Kalibrr
5. Glints
6. Career Sites: web karier perusahaan, ATS resmi perusahaan, dan career center universitas

Portal agregator lain ditahan sebelum hydration dan tidak masuk analisis. Mesin membuat dua kelompok jabatan untuk setiap sumber, maksimal 12 request pencarian per live run. Setiap query dijaga di bawah batas Brave Search API: 400 karakter dan 50 kata.

Diagnostics menampilkan sumber setiap lowongan dan jumlah penerimaan per sumber.
