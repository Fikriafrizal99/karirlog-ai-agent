# KarirLog AI Agent V1.0 — Final Status

## Completed

- Core pipeline.
- Live collector and fallback.
- AI analysis and deterministic guardrail.
- CV selector and validator.
- Application package builder.
- Gmail OAuth draft creation.
- Two-step approved email send.
- Portal prefill assistant with manual submit.
- SQLite tracker and audit trail.
- Telegram summaries.
- Windows scheduler scripts.
- Legacy database migration.
- 28 automated tests.
- Integrated duplicate dry run.

## Default safety state

- Gmail disabled until configured.
- Gmail send mode `draft_only`.
- Maximum 10 drafts per run.
- Maximum 5 sent emails per day.
- Approval expires after 30 minutes.
- Portal submit mode `manual_only`.
- Scheduler disabled until explicitly enabled.
- Telegram disabled until explicitly enabled.

## User-owned setup still required

- Insert real CV files.
- Fill profile email and phone.
- Add API keys as needed.
- Add Google OAuth credentials for Gmail.
- Complete portal login/CAPTCHA/OTP manually.
