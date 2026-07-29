# Release Notes — KarirLog AI Agent V0.3

## Added

- OpenAI Responses API provider.
- Strict structured JSON analysis.
- AI/rule/fallback analysis modes.
- Requirement and seniority extraction.
- Missing hard requirement analysis.
- Transferable strength and red flag analysis.
- Deterministic final decision guardrail.
- AI readiness command and Windows script.
- Extended SQLite analysis and run schema.
- Per-application `analysis.json`.
- Database migration from previous schemas.

## Preserved

- V0.2 live collector.
- Cross-source and historical deduplication.
- CSV fallback.
- Draft-only application package.
- JSON and Telegram reports.

## Safety

- No auto-send or browser apply.
- No contact details or CV content sent to AI.
- OpenAI request uses `store: false`.
- AI cannot bypass hard guardrail.
