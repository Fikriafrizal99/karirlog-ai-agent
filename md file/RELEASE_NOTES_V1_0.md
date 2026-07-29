# Release Notes — KarirLog AI Agent V1.0

## Added

- Gmail OAuth Desktop integration.
- Gmail draft creation dengan attachment CV.
- Two-step email approval dan approved send.
- Portal Assistant berbasis Playwright.
- Dedicated browser profile dan screenshot sebelum submit.
- Manual portal submitted confirmation.
- Windows Task Scheduler installer/uninstaller.
- Delivery Telegram summary.
- Application audit trail.
- Database migration untuk delivery fields dan events.
- 9 automated tests baru; total 28 tests.

## Changed

- Package version menjadi 1.0.
- Auto apply mode menjadi `guarded_delivery`.
- Application status sekarang mencakup Gmail dan portal delivery lifecycle.
- README dan PRD diperbarui menjadi end-to-end V1.0.

## Safety

- Gmail default `draft_only`.
- Email send memerlukan approval code.
- Portal submit tetap manual.
- Tidak ada CAPTCHA/OTP bypass.
- Secret, CV, database, OAuth token, dan browser profile tidak disertakan dalam release.
