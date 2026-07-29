# Security dan Privacy

Jangan commit atau membagikan:

- `.env`
- `credentials.json`
- `data/secrets/gmail_token.json`
- CV PDF
- SQLite database
- Browser profile

Gunakan OAuth client milik sendiri. Hapus token lokal untuk mencabut sesi aplikasi. Jangan memakai default Chrome user profile untuk Playwright; gunakan folder khusus yang sudah dikonfigurasi.

KarirLog mengirim deskripsi lowongan dan profil skill terbatas ke provider AI. File CV dan data kontak tidak dikirim ke provider AI.
