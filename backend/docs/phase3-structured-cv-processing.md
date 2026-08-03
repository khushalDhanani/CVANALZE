# Phase 3 Structured CV Processing

## Compatibility façade

`app.services.document_parser` remains the stable import surface for:

- `MarkdownGenerator` and `MarkdownResult`;
- `TextSanitizer`;
- `QualityMetricsCalculator`;
- `ResumeJsonExtractor`.

Their implementations now live in focused document-conversion, text-normalization, quality-metrics, and field-extraction modules. Existing imports and method signatures remain compatible.

## Additive normalized resume contract

The legacy `resume_json` fields remain unchanged. A typed `normalized` object is added inside `resume_json`, and the same model is exposed as `normalized_resume` on completed CV results and enriched match responses.

`EXTRACTION_SCHEMA_VERSION` is bumped to `2.0.0`, ensuring existing Phase 2 extraction and match caches cannot suppress the new additive structure.

Every normalized value includes the original value, normalized value, confidence, and source evidence. The model covers:

- lower-cased, whitespace-free email normalization;
- compact phone representation while retaining the original formatting;
- canonical skill names and aliases;
- normalized education degree, domain, institution, dates, and grade;
- employment title, company, date interval, current-role status, and duration;
- date-derived and explicitly stated experience with validation status.

## Experience authority

Employment dates are the authoritative experience source. Overlapping intervals are merged before total experience is calculated.

Explicit statements such as “five years of experience” validate the date-derived result and are recorded as corroborating or conflicting evidence. They do not overwrite the calculated duration. LLM experience is used only when neither dated experience nor a supplied deterministic candidate experience is available.

## One-context matching flow

For each analysis, `MatchService` now:

1. Uses a supplied structured resume or extracts it once for raw-text requests.
2. Builds one `CandidateAnalysisContext` containing normalized resume data, deterministic experience, taxonomy, and domain state.
3. Builds each `JobEvaluationContext` once during prefiltering.
4. Reuses the same candidate and job contexts for confidence-gate scoring and final enriched scoring.
5. Applies LLM enrichment to the existing candidate context without replacing authoritative deterministic experience.
6. Uses the candidate context’s domain profile for the response instead of recomputing it after vacancy scoring.

This removes repeated resume parsing and per-vacancy candidate taxonomy/domain construction while retaining legacy scoring entry points that create contexts when callers do not supply them.

## Compatibility

- Existing upload, polling, and raw-text paths are unchanged.
- Existing result and match fields remain present.
- Normalized data is additive.
- `VacancyPreFilter.filter_vacancies` still returns dictionaries by default; context return is opt-in for `MatchService`.
- Direct `ScoringEngine.evaluate_job_match` callers remain supported without prebuilt contexts.
