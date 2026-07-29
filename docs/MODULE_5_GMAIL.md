# Modul 5 — Gmail Draft dan Approved Send

Gmail menggunakan OAuth Desktop dan scope compose. KarirLog membuat MIME email, menambahkan CV, lalu menyimpan Gmail draft ID.

Guardrail:

- Mode default `draft_only`.
- Draft harus diperiksa di Gmail.
- Approval code dibuat per application.
- Hanya hash code yang disimpan.
- Send ditolak jika status, mode, draft ID, atau code tidak cocok.
- Reanalysis yang meng-invalidasi application membuat send tidak dapat dilanjutkan.
