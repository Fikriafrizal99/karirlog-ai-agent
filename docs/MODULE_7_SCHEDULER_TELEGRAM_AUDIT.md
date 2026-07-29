# Modul 7 — Scheduler, Telegram, dan Audit

Scheduler menjalankan `scheduled_run.bat` melalui Windows Task Scheduler. Waktu dibaca dari `config/settings.json`.

Scheduled run:

1. Collect.
2. Analyze.
3. Build package.
4. Save tracker.
5. Send Telegram pipeline summary.
6. Create Gmail drafts bila diaktifkan.
7. Send Telegram delivery summary.

Scheduled run tidak melakukan approved send atau portal submit.

Audit trail menyimpan package build, Gmail draft, approval, email sent/rejected, portal prefill/failed, dan portal submitted.
