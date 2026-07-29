# Setup AI Analysis

1. Buat `.env` dari `.env.example`.
2. Isi `OPENAI_API_KEY`.
3. Jalankan `check_ai.bat`.
4. Pertahankan `analysis_mode` sebagai `ai_with_fallback` selama pengujian.
5. Jalankan `run_sample.bat` atau `run_live.bat`.
6. Periksa `analysis_mode`, `summary`, `missing_required`, `red_flags`, dan `reasons` pada run report.

## Troubleshooting

### API key missing

Normal pada mode `ai_with_fallback`. Output akan memakai `RULE_FALLBACK`.

### HTTP error atau timeout

Pipeline menggunakan fallback pada `ai_with_fallback`. Pada `ai_required`, job dicatat sebagai `ERROR` dan draft tidak dibuat.

### Model tidak tersedia

Ubah `ai_model` pada `config/settings.json` sesuai model yang tersedia pada project API pengguna.

### Data yang dikirim

Hanya target role, lokasi, skill, transferable skill, ringkasan pengalaman, pendidikan, level karier, bahasa, dan deskripsi lowongan. Kontak, nama lengkap, dan file CV tidak dikirim.
