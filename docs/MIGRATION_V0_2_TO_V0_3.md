# Migration V0.2 to V0.3

No manual database reset is required.

When V0.3 opens an older database, it adds analysis fields for provider, model, confidence, summary, seniority, requirements, transferable strengths, red flags, AI/fallback counters, and reanalysis counters.

## Existing jobs

- Jobs with no analysis can be retried.
- Jobs with `RULE_FALLBACK` or `RULE_ONLY` can be reanalyzed when an API key becomes available and `reanalyze_fallback_when_ai_ready` is true.
- Existing application records are updated rather than duplicated.
- A prior draft is marked `INVALIDATED_BY_REANALYSIS` when a newer analysis no longer allows draft creation.

## Recommended first run

1. Back up the old project folder.
2. Copy `.env` and real CV files into the V0.3 folder.
3. Review `config/profil.json`.
4. Run `check_sources.bat` and `check_ai.bat`.
5. Run `run_sample.bat` before `run_live.bat`.
