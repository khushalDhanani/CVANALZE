# Work Status

## Work Completed
- Added PR 9 Shadow validation tests comparing the new hybrid pipeline (`MatchService`) with the fallback heuristic scoring logic (`ScoringEngine`).
- Validated correct department matches.
- Validated wrong-department candidates.
- Validated cross-domain candidates.
- Validated freshers (0 years experience).
- Validated incomplete CVs.
- Validated incomplete vacancies.
- Validated candidates with no suitable vacancy.
- Ensured all tests pass using `pytest`.

## Files Changed
- `tests/test_shadow_validation.py` (NEW)

## Pending Work
- None for PR 9.

## Important Decisions
- Shadow validation tests are implemented asynchronously utilizing standard mocks on `EmbeddingService` and `OllamaLLMService` to guarantee fast test execution while ensuring that the data pathways remain deterministic across the new `MatchService` and old `ScoringEngine`.
