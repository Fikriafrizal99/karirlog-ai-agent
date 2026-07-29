# Release Notes — KarirLog AI Agent V0.4

## Added

- Configurable CV library.
- CV file validation and SHA-256.
- Deterministic CV selection scoring.
- Ambiguity and low-confidence guardrail.
- Email/portal destination resolution.
- Attachment copying.
- Application package manifest.
- `check-cv` command and `check_cv.bat`.
- `list-applications` command and `list_applications.bat`.
- Application readiness statistics.
- Rebuild incomplete package using saved analysis.

## Changed

- Application Builder now returns structured package status.
- Database application records include CV and destination metadata.
- Telegram/run summary includes CV readiness.
- Generated package folders are rebuilt cleanly to avoid stale attachments.
- Version updated to `0.4.0`.

## Preserved

- Live collector V0.2.
- AI analysis and fallback V0.3.
- Deterministic decision guardrail.
- SQLite migration.
- Draft-only safety.

## Not Included

- Gmail send.
- Portal browser automation.
- Automatic CV rewriting.
- Scheduler.
