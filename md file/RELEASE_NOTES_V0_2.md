# Release Notes — KarirLog AI Agent V0.2

## Added

- Brave Web Search collector.
- Direct URL collector.
- RSS/Atom collector.
- JSON-LD `JobPosting` parser.
- Search result fallback parser.
- Request timeout, retry, and explicit user agent.
- Cross-source deduplication.
- URL canonicalization.
- Collector status report.
- `collector_runs` database table.
- Database migration from V0.1.
- `live`, `live_with_fallback`, `sample`, and `all` modes.
- `check-sources` command.
- `collect` command.
- Windows scripts for live, sample, collect, and source check.

## Changed

- Default discovery mode becomes `live_with_fallback`.
- CSV becomes sample/fallback source instead of the only source.
- Pipeline report now includes collector health and fallback status.
- Job data includes source ID, employment type, salary, and remote flag.

## Safety

- Auto apply remains `draft_only`.
- Missing search key becomes `SKIPPED`, not a fatal pipeline error.
- Collector failures are isolated.
- Existing lowongan are not processed twice.

## Test Result

- Unit tests: 8 passed.
- Source check: passed.
- Sample collection: passed.
- Full dry run: passed.
- V0.1 database migration: passed.
