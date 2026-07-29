# Portal Assistant V3

Portal Assistant V3 menggunakan Chrome/Edge normal dengan profil khusus untuk
menyelesaikan masalah login yang sering terjadi pada browser yang langsung
diluncurkan oleh Playwright.

## Login

```bat
portal_login.bat
```

Login dilakukan manual. Browser harus tetap terbuka ketika queue dijalankan.

## Queue

```bat
assist_portal_queue.bat
```

Queue mengambil application portal yang masih pending dan mengurutkannya
berdasarkan Application ID menaik.

```bat
assist_portal_queue.bat 5
```

Perintah tersebut hanya memproses maksimal lima application.

## Batas otomatisasi

KarirLog dapat mengisi nama, email, telepon, cover letter, dan input file yang
terdeteksi. Pengguna tetap menangani login, pilihan screening, CAPTCHA, OTP,
perpindahan halaman, serta tombol submit.
