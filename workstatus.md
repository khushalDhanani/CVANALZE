# Work Status

## Work Completed
1. **2026-08-13 Scratch File Removal — `test_unknown_fallback.py`**:
    - Reviewed and removed the isolated tracked scratch script `backend/test_unknown_fallback.py`; it contained a developer-machine-specific path, top-level print diagnostics, no assertions, and had no repository references.
    - Left the other Phase 1 candidate files unchanged and did not run builds or tests.
1. **2026-08-13 RQ Worker Restart Collision Diagnosis**:
    - Confirmed the rebuilt Compose worker is restart-looping because Redis retained the old `cv-processing-worker-1` registration from hostname `4b08976a7b87`.
    - Confirmed there is only one Compose CV worker container and the stale registration has a short TTL; no queued-job data was removed and no cleanup command was executed.
1. **2026-08-13 Docker Deployment Command Handoff**:
    - Confirmed the Compose migration service is `migrate-postgres` and provided the migration plus backend rebuild/recreate commands; no commands were executed.
1. **2026-08-13 Hiring Risks Integrity Remediation**:
    - Added normalized PostgreSQL persistence and runtime hydration for arbitrary Hiring Risk policies, including explicit enabled, category, title, source, severity, and manual-review settings.
    - Reworked risk generation around typed `RiskEvidenceEvent.failure_code` identities, with distinct disabled/unknown handling and an explicit education-integrity deferral boundary.
    - Added the versioned PostgreSQL `hiring_risk_explanation` prompt contract and constrained Gemma output to `risk_code`, `title`, and `explanation`; deterministic risk fields remain authoritative.
    - Added prompt-content, prompt-version, model, and policy-version cache identities across LLM generation, match-result reuse, persistence parity, and API reads.
    - Added stale-risk suppression for persisted results and protected-data sanitization for the narrowly scoped Gemma payload.
    - Added focused tests for dynamic policy hydration, tamper rejection, protected-data exclusion, failure isolation, cache-key invalidation, and stale persistence behavior.
    - Per repository instructions, did not run tests/builds, apply migrations, restart services, or mutate live PostgreSQL/cache state.
1. **2026-08-13 End-to-End Hiring Risks Integrity Audit (No Fix Applied)**:
    - Traced deterministic failures through `HiringRiskAnalyzer`, PostgreSQL rule hydration, `PromptService`, the centralized Ollama transport, match/result caches, PostgreSQL result persistence, API output, and frontend rendering.
    - Confirmed the live active rule profile is `system-default-v3`, but it contains no Hiring Risks component; `_hydrate_profile` also has no Hiring Risks branch.
    - Confirmed PostgreSQL contains no `hiring_risk_explanation` prompt row, so the live path uses deterministic explanations and makes no Hiring Risks Gemma call.
    - Found that disabled and unknown policies are represented identically, explanation cache identity omits prompt/model/policy versions, and persisted-result reuse can retain stale risks.
    - Confirmed Hiring Risks are already modeled and rendered by the frontend, and the API returns the persisted match-analysis structure without recalculating risks.
    - No application code, database data, cache data, build, service, or test was changed or executed; only read-only source inspection and PostgreSQL queries were performed.
1. **2026-08-12 Matching Failure Diagnosis (No Fix Applied)**:
    - Traced the supplied worker log to an incomplete tri-state hierarchy migration in commit `7e86c81`.
    - Confirmed `HierarchyClassificationResult.is_hierarchy_valid` and `DynamicTaxonomyService` can emit `None`, while `VacancyFitScoreBreakdown.is_hierarchy_valid` still requires `bool`.
    - Confirmed the resulting Pydantic validation error is caught per vacancy in both scoring passes, causing empty match results while the outer RQ job is still reported as successful.
    - Identified a related static regression: `VacancyFitEvaluator.classify_opening_fit` now trusts the stored status and no longer rejects an explicit `is_hierarchy_valid=False`, contrary to the added tri-state test.
    - Identified a separate non-retryable Ollama HTTP failure affecting optimized matching; the log omits the HTTP status/body, but the request sends `think=True` to `gemma3:4b`, making model capability/request incompatibility the leading cause.
    - No application code was changed and no build, run, or tests were executed.
2. **Hierarchy Validation Fix**:
    - Updated the hierarchy-classification schema and producer to use tri-state logic (`True`, `False`, `None`); the downstream score-breakdown schema was missed, as documented above.
    - Added `test_hierarchy_valid_tri_state` to ensure correct handling of all 3 states.
    - Corrected match service logs to clearly separate domain validity, hierarchy validity, and final genuine match decisions.
3. **Seed Data Migration**:
    - Audited and converted all legacy string keywords in `department_domains_seed.json` to the new `KeywordConfig` schema (`term`, `match_type`, `weight`).
    - Configured "IT" as a `CASE_SENSITIVE_ACRONYM` to fix the false-positive pronoun bug.
4. **Taxonomy Fix Validation**:
    - Verified that short-acronyms like HR and QA correctly maintain recall as `CASE_INSENSITIVE_TOKEN`.
    - Added/updated tests in `test_domain_matching.py` (`test_case_insensitive_lowercase_qa`, `test_genuine_active_vacancy_match`) and resolved test mock mismatches to ensure the new matching engine passes unit validation.
5. **Hiring Risks and Concerns Architecture (Chunk 9B)**:
    - Added `HiringRisk` schema and dynamic `HiringRiskConfig` to `app/core/rule_config_manager.py` to drive risk severity and policies.
    - Implemented `HiringRiskAnalyzer` to deterministically translate evaluation gaps (Missing Skills, Minimum Experience, Domain Caps, Unparseable Experience) into structured risks.
    - Integrated Gemma (`OllamaLLMService._execute_structured_generation`) to act merely as a human-readable explanation translator for the deterministic evidence. 
    - Forced all AI generation to respect strict JSON schema guarantees and ignore any hallucinated risks.
    - Verified all edge-cases via a robust test suite (`tests/test_hiring_risk_analyzer.py`), confirming that score and match states remain entirely immutable during this phase.

## Pending Work / Side Effects Found
- Apply `backend/scripts/migrations/postgres/025_hiring_risks_integrity.sql` through the normal deployment process, then restart application/worker processes so the active policy and prompt are loaded.
- Run the focused Hiring Risks tests and the broader regression suite when execution is authorized; tests were added but intentionally not executed during this task.
- Fix is intentionally pending per the diagnostic-only request: align hierarchy nullability across backend/API/frontend and restore the explicit `False` hard-rejection behavior.
- Capture/log the sanitized Ollama HTTP status and response detail to confirm the exact optimized-match 4xx cause; review `think=True` compatibility with `gemma3:4b`.
- The full test suite (`pytest tests/`) reported 72 failures (out of 624 tests) previously regarding schema updates. These are still pending structural fix actions.
- *Side Effect Found* -> Legacy Tests expecting old keyword structures -> *Required Adjustment*: Update mocks in `test_classification_normalization.py`, `test_department_domain_repository.py`, and other taxonomy tests.

## Important Decisions
- Kept risk identity and all decision fields deterministic; Gemma can update only recruiter-facing title and explanation for risk codes already emitted by the analyzer.
- Treat unknown policies as safe ignored events, disabled configured policies as explicitly suppressed events, and education evidence as deferred regardless of policy configuration.
- Suppress stale persisted Hiring Risks instead of recalculating them in repository/API layers; full CV processing remains the single generation path.
- Included prompt content identity in addition to its version tag so an in-place prompt edit cannot reuse an old explanation cache entry after PromptService invalidation.
- Treated the audit as diagnostic-only and did not apply fixes, execute tests/builds, mutate the live database, or clear caches.
- Used the running PostgreSQL container only for read-only verification of active prompt and rule-profile state.
- Kept this task diagnostic-only: no application fixes, test execution, build, service run, cache mutation, or database operation was performed.
- Kept the `department_domain_repository` loading logic intact to respect the existing data-driven workflow, modifying only the seed initialization schema.
- Added `QA Team` to the `conftest.py` repository mock to allow `test_domain_matching.py` to properly test case-insensitive matching for `qa`.
- To guarantee we don't break fallback taxonomy matching logic but maintain proper capitalization intent, only words `len <= 3` and strictly `.isalpha()` are routed to case-sensitive acronym generation.
- Original casing is injected natively into `CandidateResumeDTO` during initialization, replacing forced lowercasing. The regular keyword matching ignores the original casing anyway via `re.IGNORECASE`, minimizing any blast radius across legacy domain matchings.
- The `HiringRiskAnalyzer` relies strictly on deterministic `match_result` failures; Gemma acts purely as an explanation generator, preserving full explainability and pipeline integrity.

## Files Changed
- `backend/test_unknown_fallback.py` (removed)
- `backend/app/services/configuration_service.py`
- `backend/app/services/cv_service.py`
- `backend/app/services/match_service.py`
- `backend/app/services/prompt_service.py`
- `backend/app/repositories/result.py`
- `backend/scripts/seed_prompts.py`
- `backend/scripts/migrations/postgres/025_hiring_risks_integrity.sql`
- `backend/scripts/migrations/postgres/025_hiring_risks_integrity_down.sql`
- `backend/tests/conftest.py`
- `backend/tests/test_cache_hit_persistence.py`
- `backend/tests/test_configuration_schema.py`
- `backend/tests/test_prompt_service.py`
- `workstatus.md`
- `backend/app/repositories/department_domain.py`
- `backend/app/services/job_taxonomy.py`
- `backend/app/services/candidate_domain_service.py`
- `backend/tests/test_domain_matching.py`
- `backend/tests/conftest.py`
- `backend/app/schemas/match.py`
- `backend/app/core/rule_config_manager.py`
- `backend/app/services/system_rule_config_factory.py`
- `backend/app/services/hiring_risk_analyzer.py`
- `backend/app/services/scoring_engine.py`
- `backend/tests/test_hiring_risk_analyzer.py`
