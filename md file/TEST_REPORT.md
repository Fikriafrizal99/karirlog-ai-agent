# Test Report — KarirLog AI Agent V1.0

## Automated test

Command:

```text
PYTHONPATH=src python -m unittest discover -s tests -v
```

Result:

- Tests run: 28
- Passed: 28
- Failed: 0
- Errors: 0

Coverage scenarios:

- JobPosting JSON-LD parsing.
- URL canonicalization.
- Cross-source fingerprint.
- RSS and URL collector.
- CSV fallback.
- AI structured output mock.
- Rule fallback.
- Seniority and requirement guardrail.
- Database migration.
- Reanalysis without duplicate application.
- CV matching, missing CV, ambiguity, attachment, and manifest.
- Gmail MIME recipient/sender/attachment.
- Gmail draft result parsing.
- Wrong approval rejection.
- Approved send.
- End-to-end Gmail delivery database status and audit.
- Portal prefill workflow mock and manual-review status.
- Scheduler time validation.

## Integrated dry run

Input: four sample jobs.

Run 1:

- Unique jobs: 4
- New jobs: 4
- APPLY: 2
- SKIP: 2
- Application packages: 2
- Email-ready packages: 2

Run 2:

- Duplicate history: 4
- New applications: 0
- Duplicate packages: 0

Scheduled run with Gmail disabled:

- Pipeline completed.
- Existing jobs remained deduplicated.
- Two email applications were safely skipped by delivery because Gmail was disabled.

## Live integration not executed in build environment

The release environment did not contain the user's:

- OpenAI API key.
- Brave Search API key.
- Google OAuth credentials.
- Telegram token/chat ID.
- Portal login session.

Live HTTP and browser actions therefore require user-owned credentials after installation. All related paths were tested with deterministic mocks and validation logic.
