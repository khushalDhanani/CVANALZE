# Work Status

## Work Completed
1. **2026-08-13 Legacy Mandatory-Failure Response Compatibility Fix**:
    - Traced the `POST /api/match/upload` 500 to completed cached analysis records created before `MandatoryFailureDetails.failure_code` became required.
    - Added centralized schema hydration that preserves current explicit codes and derives the current evaluator code for legacy skill, experience, certification, CTC, and domain failures.
    - Assigned unknown historical requirement types the neutral `LEGACY_MANDATORY_FAILURE` identity instead of rejecting the entire completed response or inventing a specific risk category.
    - Added focused regression coverage for the logged minimum-experience payload, nested best/unsuitable openings, current-code preservation, every supported legacy mapping, and the neutral fallback.
    - Per repository instructions, did not run backend tests, builds, migrations, or services.
1. **2026-08-13 Default Hiring Risk Prompt and Identity**:
    - Added a centralized built-in `hiring_risk_explanation` prompt fallback in `PromptService`, using version `default-1.0.0` and a stable SHA-256 content identity.
    - Kept active PostgreSQL prompt records authoritative; the built-in default is used only when no compatible active record exists or database prompt lookup is unavailable.
    - Updated unversioned and versioned prompt resolution plus provenance lookup so runtime generation, CV persistence, match-cache identities, and candidate detail metadata all resolve the same default.
    - Made stale cached `__MISSING__` version/identity markers resolve to the built-in default instead of continuing to emit `missing` until cache expiry.
    - Reused the centralized default template from the maintained prompt seeder and aligned `HiringRiskAnalyzer.PROMPT_NAME` with the same centralized constant.
    - Replaced literal `missing` values on legacy candidate-detail provenance with honest default-availability messages; the UI directs reprocessing before claiming the default version or identity was historically recorded.
    - Added focused regression coverage for default prompt content, version, identity, cached-missing recovery, and analyzer prompt-name alignment.
    - Per repository instructions, did not run backend tests, builds, migrations, or services.
1. **2026-08-13 Candidate Detail Card Visibility Fix**:
    - Traced invisible candidate-detail cards to conditional rendering that omitted Hiring Risks for empty arrays, omitted processing provenance for legacy records, and provided no explanation when canonical fit metadata was absent.
    - Made the top vacancy's Hiring Risks card visible with an explicit no-active-risk state when no deterministic policy fires, while preserving omission for non-top matches without risks.
    - Made Processing Provenance visible on both the default Overview tab and Processing Pipeline tab; legacy results now show every version field as `Not recorded` with a reprocessing explanation.
    - Added a canonical-fit unavailable state for stored results that predate hierarchy score-breakdown metadata.
    - Extracted processing provenance normalization into a reusable utility and added regression coverage for legacy and current result payloads.
    - Per repository instructions, did not run frontend tests, lint, type-check, build, or services.
1. **2026-08-13 Frontend Parity for Today's Backend Implementations**:
    - Added explicit frontend contracts for versioned hiring-risk policies and backend processing provenance.
    - Extended the active Engine Configuration screen to create, edit, enable/disable, classify, require manual review for, and remove hiring-risk policies through the existing full-profile version creation and activation workflow.
    - Expanded Hiring Risks cards with severity, category, stable risk code, deterministic source, deduplicated evidence, and complete styling for `LOW` and `UNKNOWN` severities.
    - Added a distinct informational state for unavailable hierarchy validation while preserving the backend rule that only an explicit mismatch rejects or penalizes a match.
    - Added an administrator-facing Processing Provenance card for matching, rule configuration, hiring-risk policy/prompt, optimized prompt, and LLM model versions.
    - Added focused source-level regression tests for policy preservation, risk evidence presentation, and all hierarchy-validation states.
    - Reviewed the Expo SDK 57 reference before implementation; no new SDK dependency or platform API was required.
    - Per repository instructions, did not run frontend tests, lint, type-check, build, or services.
1. **2026-08-13 Frontend Gap Audit for Today's Backend Implementations**:
    - Compared today's hiring-risk policy, hierarchy tri-state, recommendation, optimized-match, Ollama transport, migration, and worker-identity changes with the frontend types, services, configuration screens, candidate detail views, and focused frontend tests.
    - Confirmed the recommendation nullability fix, optimized-match budget/telemetry, Ollama response handling, migration execution, and RQ worker identity changes do not require frontend contract changes.
    - Identified the missing active-profile editor and explicit frontend types for versioned hiring-risk policies, incomplete risk evidence/category/source presentation, missing processing-version metadata presentation, and missing visual treatment/test coverage for unknown hierarchy validation.
    - Kept the audit diagnostic-only; no frontend application code, tests, builds, or services were changed or executed.
1. **2026-08-13 Docker Ollama Model Alignment to Llama 3.2**:
    - Confirmed the newly installed local generation model is `llama3.2:3b` while the running API and worker containers still use `gemma3:1b`.
    - Updated the repository-root `.env`, the single Docker model source, to `OLLAMA_MODEL=llama3.2:3b`.
    - Confirmed the application default and environment template already use `llama3.2:3b`; no duplicate model setting was introduced.
    - Did not recreate containers, so the running API and worker remain on `gemma3:1b` until deployment is authorized.
1. **2026-08-13 Nullable Canonical Experience Recommendation Fix**:
    - Traced the `/api/recommendations/candidate/cv_1764311881` failure to `RecommendationService` converting the canonical unknown experience duration (`None`) with `float(None)`.
    - Preserved the canonical experience engine's four-state contract instead of coercing unknown duration to zero.
    - Limited the low-experience risk flag to known numeric durations so documented employment with unavailable dates is not mislabeled as limited experience.
    - Added focused regression coverage for recommendations with documented employment and unparseable dates.
    - Per repository instructions, did not rebuild, restart, or test services.
1. **2026-08-13 Optimized Match Output Budget Fix**:
    - Confirmed `optimized_match` explicitly requested 2,048 output tokens but shared the 4,096-token general context window, leaving only about 1,677 tokens after the observed 2,419-token prompt.
    - Added a dedicated 8,192-token optimized-match context and raised its explicit output allowance to 3,072 tokens, leaving about 2,701 tokens of additional headroom for prompt framing and schema overhead at the observed prompt size.
    - Added centralized success and truncation telemetry for response characters, actual output tokens, `num_predict`, and `num_ctx`.
    - Made output-limit failures non-retryable because repeating an identical deterministic request with unchanged limits cannot complete the response.
    - Added configuration validation and focused payload/retry regression coverage.
    - Ran the two explicitly requested focused regression tests: 2 passed with 2 unrelated Redis-client deprecation warnings; did not build, start, or restart services or run the full suite.
1. **2026-08-13 Vacancy Hierarchy Tri-State Validation Fix**:
    - Traced repeated vacancy matching failures to `HierarchyClassificationResult.is_hierarchy_valid=None` being passed into a score-breakdown schema that accepted only booleans.
    - Aligned the vacancy-fit response schema and frontend API type with the existing tri-state hierarchy contract: `true` is valid, `false` is invalid, and `null` means validation was unavailable.
    - Preserved scoring behavior so only an explicit `false` triggers hierarchy rejection; an unknown value remains eligible for the other deterministic gates.
    - Added focused regression coverage for preserving the unknown hierarchy-validation state.
    - Per repository instructions, did not build, run, restart, or test services.
1. **2026-08-13 RQ Worker Registration Collision Fix**:
    - Traced the auxiliary-worker restart loop to the fixed `cv-analyzer-auxiliary-worker` name colliding with an existing active/stale Redis registration.
    - Added a shared collision-resistant RQ identity builder that retains stable role prefixes and appends a per-process UUID.
    - Applied unique identities consistently to auxiliary and primary CV workers, eliminating the same latent restart collision without deleting Redis workers, queues, or jobs.
    - Added worker startup logging for the resolved identity and focused tests for worker wiring, stable prefixes, uniqueness, and invalid roles.
    - Per repository instructions, did not build, run, restart, or test services.
1. **2026-08-13 PostgreSQL Migration JSON Bind-Parsing Fix**:
    - Diagnosed migration 025 failure as SQLAlchemy `text()` interpreting JSON tokens such as `:true` and `:false` as bind parameters.
    - Added one raw-driver migration execution helper for trusted repository SQL files and routed both forward and rollback scripts through it.
    - Preserved parameterized SQLAlchemy execution for migration-history queries and writes.
    - Kept migration 025 unchanged; its failed transaction was not recorded as applied and can be retried after rebuilding the migration image.
    - Added focused regression coverage proving JSON literals are passed unchanged without bind-parameter parsing.
    - Per repository instructions, did not rerun migrations, tests, builds, or services.
1. **2026-08-13 Ollama Response Integrity Remediation**:
    - Removed Qwen-specific thinking directives from maintained prompt seeds and removed the obsolete duplicate optimized prompt from the generic seeder while preserving the checksum of already-issued migration 024.
    - Added versioned PostgreSQL migration 026 to activate model-neutral optimized prompt version `3.6`, remove legacy directives from generic prompts, and invalidate version-bound caches safely.
    - Added centralized defensive removal of legacy first-line thinking directives and prompt-readiness rejection for incompatible active optimized prompts.
    - Versioned the optimized prompt cache key so persisted `3.5` cache entries cannot shadow the corrected `3.6` database prompt.
    - Preserved bounded, whitespace-normalized Ollama error details for HTTP and JSON error envelopes and included status, retryability, and safe detail in transport/generation fallback logs.
    - Added explicit deterministic-fallback and embedding-throttle logging so missing LLM/embedding results no longer disappear silently.
    - Aligned Docker and local generation deadlines at 90 seconds and made the Docker request/generation timeout values required root-environment inputs.
    - Added focused regression coverage for sanitized server detail, JSON error envelopes, legacy prompt normalization, prompt readiness, native thinking-model behavior, and throttle observability.
    - Per repository instructions, did not run tests, builds, migrations, or services.
1. **2026-08-13 End-to-End Ollama Response Audit (No Fix Applied)**:
    - Confirmed all Ollama HTTP traffic is centralized in `OllamaTransport`: generation and unload use `/api/generate`, embeddings use `/api/embed`, and discovery uses `/api/tags`.
    - Confirmed generation sends `stream=false`, reads the complete response body, and parses one JSON object; a live local request using the repository payload shape returned the expected non-streaming envelope and structured JSON response.
    - Confirmed the configured generation model `llama3.2:3b` and embedding model `nomic-embed-text` match the locally installed `llama3.2:3b` and `nomic-embed-text:latest` models.
    - Found the versioned optimized-match PostgreSQL prompt migration still stores a leading `/think` directive, so the active Gemma request can retain Qwen-specific prompt content despite transport-level capability handling.
    - Found HTTP and JSON error handling discards Ollama's diagnostic error body, logs only exception class names, then converts generation failure to `None`; optimized matching consequently continues without an LLM result.
    - Found embedding connection/model failures activate a 60-second model throttle whose subsequent early returns are not logged.
    - No application code, migrations, database state, builds, tests, or services were changed or executed; only read-only source, local model inventory, and one minimal local generation request were used.
1. **2026-08-13 Gemma 3 Ollama Generation Compatibility Fix**:
    - Centralized thinking-capability resolution in `OllamaLLMService` for recognized thinking model families.
    - Removed Qwen-specific `/think` and `/no_think` prompt prefixes from the shared structured-generation path.
    - Changed the centralized generation payload builder to omit `think` for Gemma 3 and other non-thinking models while preserving native `think` requests for supported models.
    - Kept `/api/generate`, `/api/embed`, model selection, retries, caching, timeouts, and response contracts unchanged.
    - Updated focused payload tests for `llama3.2:3b` and added coverage ensuring a Qwen 3 model retains the native thinking parameter.
    - Per repository instructions, did not run tests, builds, services, or migrations.
1. **2026-08-13 Docker Ollama Model Source Consolidation**:
    - Set the repository-root Docker environment override to `OLLAMA_MODEL=llama3.2:3b`.
    - Changed `docker-compose.yml` to require `OLLAMA_MODEL` from the repository-root environment instead of maintaining a second fallback value.
    - Removed the competing `qwen3:1.7b` declaration from `docker-compose.local.yml`; local Compose now inherits the required base environment value.
    - Updated local-profile documentation to use the inherited model instead of supplying another command-line model override.
    - Confirmed application integrations continue consuming the resolved model through `app.core.config.settings`.
    - Per repository instructions, did not build, test, start, or recreate Docker services.
1. **2026-08-13 Docker Ollama Model Configuration Check (No Fix Applied)**:
    - Confirmed the centralized application default, primary Compose fallback, backend example environment, README, and current backend-local environment use `llama3.2:3b`.
    - Found the repository-root `.env` still sets `OLLAMA_MODEL=gemma3:4b`; Docker Compose interpolation therefore overrides the `llama3.2:3b` fallback in `docker-compose.yml`.
    - Found `docker-compose.local.yml` still has a `qwen3:1.7b` fallback, although the current root `.env` value takes precedence when that override is used.
    - No Docker services, builds, tests, or application configuration files were changed or executed.
1. **2026-08-13 Backend/Test Dead-Artifact Cleanup**:
    - Audited tracked and untracked files under `backend/` and `backend/tests/` against Python imports, dynamic path loading, Docker/Compose, CI, migrations, documentation, and tests.
    - Removed unreferenced root-level scratch probes, hardcoded candidate/vacancy diagnostics, source-rewriting patch helpers, one-off cache/database commands, a generated audit log, and a print-only debug test.
    - Moved three assertion-based root tests into `backend/tests/` instead of deleting their coverage: education requirement matching, relevant experience, and score ownership.
    - Preserved runtime entry points, maintained operational scripts, all PostgreSQL migrations, `uv.lock`, `department_domains_seed.json`, and `tests/mock_rule_config.py`.
    - Verified no remaining repository reference names a removed artifact and `git diff --check` passes.
    - Ran the complete backend suite: 571 tests passed and 106 failed. Collection and execution complete without deleted-module/import failures; existing functional failures remain across taxonomy, extraction, scoring, configuration, and Hiring Risks behavior.
    - Ran Ruff across application, tests, entry points, and scripts; it reports 362 pre-existing lint findings (308 auto-fixable), so no unrelated bulk formatting was applied.
1. **2026-08-13 Scratch File Removal — lexical/plant diagnostics**:
    - Removed `backend/test_lexical_1215.py`, which duplicated lexical scoring for fixed candidate/vacancy IDs and executed live database work during pytest import.
    - Removed `backend/check_plant_exp.py`, an unreferenced module-level database inspection hardcoded to `Plant Assistant - I`.
    - Reconfirmed `backend/requirements.txt` and `backend/workstatus.md` remain removed while `backend/uv.lock` and `backend/app/data/department_domains_seed.json` remain present.
1. **2026-08-13 Scratch File Removal — `test_top10.py`**:
    - Removed the tracked candidate-specific top-10 ranking experiment that ran live PostgreSQL, embedding, and vacancy-prefilter operations during module import.
    - Confirmed it had no assertions or repository consumers; maintained `top_k=10` coverage remains in `backend/tests/test_vacancy_prefilter.py`.
1. **2026-08-13 Scratch File Removal — `test_rrf_rank.py`**:
    - Removed the tracked candidate/vacancy-specific RRF diagnostic that performed live PostgreSQL, embedding, pgvector, and vacancy-prefilter operations during module import.
    - Confirmed it had no assertions or repository consumers and overlapped maintained ranking/prefilter coverage under `backend/tests/`.
1. **2026-08-13 Scratch File Removal — `test_candidate_1760668444.py`**:
    - Removed the tracked candidate-specific diagnostic that queried PostgreSQL and ran `MatchService.analyze_single_cv()` at module import through `asyncio.run()`.
    - Confirmed it had no assertions, reusable pytest tests, or repository consumers; other candidate-specific scripts were left unchanged pending individual review.
1. **2026-08-13 `test_unknown_fallback.py` Removal Verification**:
    - Reconfirmed `backend/test_unknown_fallback.py` is absent, has no remaining repository references, and can no longer be imported by pytest discovery.
1. **2026-08-13 Repository Artifact Cleanup — Phases 2–4**:
    - Removed the redundant generated `backend/requirements.txt`; `backend/pyproject.toml` and `backend/uv.lock` remain the dependency sources used by Docker and local development.
    - Removed the corrupted, superseded `backend/workstatus.md`; this root file remains the canonical work log required by `AGENTS.md`.
    - Removed confirmed broken or obsolete database-analysis, candidate-specific cleanup, legacy embedding, MSSQL-write, code-generation, phase-one migration, and historical-shadow scripts.
    - Removed the confirmed legacy CVAI cutover export/import/backfill helpers and the out-of-band MSSQL dependency/drop scripts.
    - Preserved all runtime, bootstrap, evaluation, regression, and PostgreSQL migration assets, including `department_domains_seed.json`.
    - Documented retained bootstrap/seed and manual evaluation/reprocessing commands in `README.md`; no build, test, migration, seed, or reprocessing command was executed.
1. **2026-08-13 Phase 4 Data/Bootstrap Deep Reference Audit**:
    - Inventoried all tracked backend JSON datasets, PostgreSQL/MSSQL migrations, and operational/bootstrap scripts, then traced static references, dynamic path loading, Docker, CI, documentation, and tests.
    - Confirmed `department_domains_seed.json` remains required by `seed_department_domains.py` and taxonomy seed-validation tests; PostgreSQL migration 005 creates its table but does not populate it.
    - Confirmed `confidence_calibration.json` is runtime-loaded, while `llm_reliability_v1.json` and `regression_cvs.json` are maintained evaluation/regression assets.
    - Classified all PostgreSQL up/down migrations, the migration runner, drift verifier, container health check, documented reset script, and current seed/evaluation scripts as retained assets.
    - Identified broken or obsolete removal candidates without deleting them: `analyze_db_schema.py`, `audit_db_integrity.py`, both legacy embedding backfills, the MSSQL-writing required-skills backfill, `generate_mssql_models.py`, `migrate_phase1_inventory.py`, and `run_historical_shadow_validation.py`.
    - Marked legacy CVAI backfill/export/import helpers plus the MSSQL dependency/drop scripts for cutover-owner confirmation before removal; no application, data, migration, or script file was changed.
1. **2026-08-13 Historical Artifact Audit — `backend/workstatus.md`**:
    - Confirmed the backend-local work log has no repository references, is not the `AGENTS.md`-mandated canonical log, and was last changed before the actively maintained root `workstatus.md`.
    - Found that it begins with a literal `<truncated 54 lines>` corruption marker and includes superseded implementation/verification claims, making it unreliable even as an unqualified archive.
    - Recommended removal rather than continued maintenance or archival; Git history already preserves the useful engineering record. No file was moved or removed during this audit.
1. **2026-08-13 Dependency File Audit — `backend/requirements.txt`**:
    - Audited tracked and untracked repository CI/CD configuration, Dockerfiles, Compose files, scripts, and documentation for `requirements.txt` and `pip install -r` usage.
    - Confirmed the maintained Docker workflow copies `pyproject.toml` plus `uv.lock` and runs `uv sync --frozen`; local/deployment documentation also uses `uv`.
    - Found no repository consumer of `backend/requirements.txt`; its only current reference is its own generated-file header.
    - Kept `backend/requirements.txt`, `backend/pyproject.toml`, and `backend/uv.lock` unchanged because external server/bootstrap configuration is outside repository visibility and still requires confirmation.
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
- Run the focused legacy mandatory-failure compatibility regression test and rebuild/recreate the API container when execution is explicitly authorized.
- Rebuild/recreate the API and worker containers, then reprocess legacy candidates whose stored provenance still contains literal `missing`; new processing will persist `default-1.0.0` and its content identity automatically.
- Run the focused frontend regression tests, TypeScript check, and lint when execution is explicitly authorized.
- Recreate the API and worker containers so `OLLAMA_MODEL=llama3.2:3b` becomes active, then verify startup model discovery.
- Rebuild/recreate the API container so nullable canonical experience is handled by the recommendations endpoint, then reload `/cv_1764311881`.
- Rebuild/recreate the API and worker containers so the optimized-match token budget takes effect, then reprocess the affected CV and confirm `done_reason=stop` in runtime logs.
- Rebuild and recreate the auxiliary and primary worker containers so their new unique RQ identities take effect; old Redis registrations can expire naturally.
- Rebuild/recreate the API and worker containers so the nullable hierarchy response contract takes effect, then reprocess the failed CV job.
- Rebuild the `migrate-postgres` image before retrying migrations; `docker compose run` alone can reuse the pre-fix image.
- Apply `backend/scripts/migrations/postgres/026_ollama_response_integrity.sql`, then rebuild/recreate backend services so prompt version `3.6`, timeout settings, and transport diagnostics become active.
- Run the focused Ollama service/transport and prompt-readiness tests when execution is authorized.
- The backend suite is not currently green: the latest full run reported 106 failures and 571 passes. This cleanup did not attempt broad product-code or substantive-test remediation.
- The three preserved legacy test modules now live under `backend/tests/`, but 7 of their 11 tests expose outdated contracts and require a separate behavioral/test-contract decision.
- Apply `backend/scripts/migrations/postgres/025_hiring_risks_integrity.sql` through the normal deployment process, then restart application/worker processes so the active policy and prompt are loaded.
- Run the focused Hiring Risks tests and the broader regression suite when execution is authorized; tests were added but intentionally not executed during this task.
- The full test suite (`pytest tests/`) reported 72 failures (out of 624 tests) previously regarding schema updates. These are still pending structural fix actions.
- *Side Effect Found* -> Legacy Tests expecting old keyword structures -> *Required Adjustment*: Update mocks in `test_classification_normalization.py`, `test_department_domain_repository.py`, and other taxonomy tests.

## Important Decisions
- Kept `failure_code` required in the canonical schema and restored only missing legacy values at validation time, preserving the current response contract and producer discipline.
- Used exact current evaluator identities for recognized historical requirement IDs and a neutral fallback for unknown legacy types to avoid inventing a specific hiring-risk classification.
- Used a code-level built-in hiring-risk prompt only as a database-unavailable fallback; active database prompt customization remains authoritative and no duplicate Ollama client or generation path was introduced.
- Derived the default prompt identity from the exact centralized template content so cache invalidation occurs automatically if that maintained fallback changes.
- Replaced silent conditional omission with explicit empty or legacy states on candidate detail; absence of risks or version metadata is now visible and distinguishable from a rendering failure.
- Kept empty Hiring Risks feedback limited to the top vacancy match so multi-match pages do not repeat a success card for every evaluated opening.
- Reused the existing full-profile configuration version workflow so hiring-risk edits remain atomic with scoring rules and activate through the backend's established audit path.
- Kept deterministic evidence separate from the recruiter-facing explanation in the UI so LLM-enhanced copy never obscures the backend facts that produced a risk.
- Exposed processing provenance only in the existing Processing Pipeline tab, keeping operational identifiers out of the primary recruiter overview.
- Classified today's frontend work as targeted parity work rather than a broad endpoint rewrite; backend-only reliability and deployment changes need no UI implementation.
- Preserved `is_hierarchy_valid=null` as eligible for normal deterministic matching while requiring distinct informational UI copy from both confirmed valid and confirmed invalid hierarchy states.
- Retained the repository-root `.env` as Docker's only Ollama model value source; Compose validates and passes it through without its own model fallback.
- Kept unknown experience duration distinct from confirmed zero experience; recommendations may display the canonical assessment but must not perform numeric comparisons on `None`.
- Gave `optimized_match` a dedicated context setting instead of increasing the context and memory footprint of every generation operation.
- Classified `done_reason=length` as non-retryable because the retry payload and deterministic generation settings are unchanged.
- Preserved hierarchy validity as a tri-state value rather than coercing unknown validation to `true` or `false`; only confirmed hierarchy mismatches are hard rejections.
- Avoided deleting or force-unregistering the existing RQ worker because Redis cannot safely distinguish a stale registration from a live worker solely by name; unique per-process names remove the collision safely.
- Execute only trusted repository migration-file contents with `exec_driver_sql`; retain bound parameters for application SQL and migration metadata operations.
- Versioned the corrected optimized prompt as `3.6` instead of editing the active `3.5` record in place so prompt-version cache identities are invalidated deterministically.
- Preserved migration 024 unchanged because the migration runner checks applied-file SHA-256 values; all database correction is isolated in forward migration 026.
- Limited persisted prompt cleanup to global model-neutral prompt records; tenant- or model-specific prompt contracts are not rewritten.
- Retained deterministic fallback behavior but made every generation fallback and embedding throttle decision explicit in logs.
- Classified the endpoint and non-streaming parser as correct based on both source inspection and a live local response; identified prompt compatibility and swallowed diagnostic context as the remaining response defects.
- Treat Ollama's `think` field as capability-specific and omit it for non-thinking models rather than sending `false`; do not mix model-specific slash directives into shared prompts.
- Kept the repository-root `.env` as the sole Docker value source for `OLLAMA_MODEL`; `docker-compose.yml` validates and passes it through, while environment-specific Compose files inherit it.
- Kept the Docker Ollama model check diagnostic-only; did not change `.env`, Compose files, or running containers without an explicit fix/redeploy request.
- Preserved assertion-based tests even when currently failing; cleanup did not hide product regressions by deleting substantive coverage.
- Removed only files with no repository consumer and clear scratch, diagnostic, generated, obsolete migration-helper, or developer-only behavior.
- Kept PostgreSQL as the only writable application database path and removed legacy helpers that imported removed engine aliases or attempted MSSQL mutation.
- Kept `department_domains_seed.json` because fresh migrations create but do not populate `DepartmentDomainMaster`; the explicit seeder and taxonomy tests still consume it.
- Kept every PostgreSQL up/down migration because the migration runner discovers them dynamically by filename.
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
- `backend/app/schemas/match.py`
- `backend/tests/test_legacy_mandatory_failure_compatibility.py`
- `workstatus.md` (legacy mandatory-failure response compatibility fix recorded)
- `backend/app/services/prompt_service.py`
- `backend/app/services/hiring_risk_analyzer.py`
- `backend/scripts/seed_prompts.py`
- `backend/tests/test_prompt_service.py`
- `backend/tests/test_hiring_risk_analyzer.py`
- `frontend/src/utils/processingProvenance.ts`
- `frontend/src/__tests__/backendParity.test.ts`
- `workstatus.md` (default hiring-risk prompt and identity recorded)
- `frontend/src/app/candidates/[id].tsx` (candidate-detail empty and legacy card states)
- `frontend/src/components/ui/HiringRisksCard.tsx` (explicit no-active-risk state)
- `frontend/src/utils/processingProvenance.ts`
- `frontend/src/__tests__/backendParity.test.ts` (processing-provenance regression coverage)
- `workstatus.md` (candidate detail visibility fix recorded)
- `frontend/src/types/api.ts`
- `frontend/src/services/configService.ts`
- `frontend/src/app/config.tsx`
- `frontend/src/app/candidates/[id].tsx`
- `frontend/src/components/ui/HiringRisksCard.tsx`
- `frontend/src/components/ui/VacancyMatchStatusBadge.tsx`
- `frontend/src/utils/hiringRisk.ts`
- `frontend/src/utils/hierarchyValidation.ts`
- `frontend/src/__tests__/backendParity.test.ts`
- `frontend/src/__tests__/hiringRiskConfig.test.ts`
- `workstatus.md` (frontend parity implementation recorded)
- `workstatus.md` (frontend gap audit for today's backend implementations recorded)
- `.env`
- `workstatus.md` (Docker Ollama model alignment to `llama3.2:3b` recorded)
- `backend/app/services/recommendation_service.py`
- `backend/tests/test_ai_recommendations.py`
- `workstatus.md` (nullable canonical experience recommendation fix recorded)
- `backend/app/core/config.py`
- `backend/app/services/llm_service.py`
- `backend/app/services/ollama_transport.py`
- `backend/.env.example`
- `.env`
- `docker-compose.yml`
- `docker-compose.local.yml`
- `README.md`
- `backend/tests/test_qwen_llm_service.py`
- `backend/tests/test_phase5_ollama_standardization.py`
- `workstatus.md` (optimized-match output budget fix recorded)
- `backend/app/schemas/match.py`
- `frontend/src/types/api.ts`
- `backend/tests/test_vacancy_fit_scoring.py`
- `workstatus.md` (vacancy hierarchy tri-state validation fix recorded)
- `backend/app/core/rq_worker_identity.py`
- `backend/start_aux_worker.py`
- `backend/start_worker.py`
- `backend/tests/test_aux_worker.py`
- `backend/tests/test_worker_cleanup.py`
- `backend/tests/test_rq_worker_identity.py`
- `workstatus.md` (RQ worker registration collision fix recorded)
- `backend/scripts/run_migrations.py`
- `backend/tests/test_migration_runner.py`
- `workstatus.md` (PostgreSQL migration JSON bind-parsing fix recorded)
- `backend/app/core/config.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/llm_service.py`
- `backend/app/services/match_service.py`
- `backend/app/services/ollama_transport.py`
- `backend/app/services/prompt_service.py`
- `backend/scripts/seed_prompts.py`
- `backend/scripts/migrations/postgres/026_ollama_response_integrity.sql`
- `backend/scripts/migrations/postgres/026_ollama_response_integrity_down.sql`
- `backend/tests/test_phase5_ollama_standardization.py`
- `backend/tests/test_prompt_service.py`
- `backend/tests/test_qwen_llm_service.py`
- `.env`
- `backend/.env`
- `backend/.env.example`
- `docker-compose.yml`
- `docker-compose.local.yml`
- `README.md`
- `workstatus.md` (Ollama response integrity remediation recorded)
- `workstatus.md` (end-to-end Ollama response audit recorded)
- `backend/app/services/ollama_transport.py`
- `backend/app/services/llm_service.py`
- `backend/tests/test_qwen_llm_service.py`
- `workstatus.md` (Gemma 3 generation compatibility fix recorded)
- `.env`
- `docker-compose.yml`
- `docker-compose.local.yml`
- `README.md`
- `workstatus.md` (Docker Ollama model consolidation recorded)
- `workstatus.md` (Docker Ollama model configuration check recorded)
- Root-level backend scratch/debug/patch/print/cache/database helper files (removed; see Git status for the complete enumerated set)
- `backend/audit_output.log` (removed generated output)
- `backend/tests/debug_test.py` (removed print-only debug test)
- `backend/test_education.py` -> `backend/tests/test_education_requirement_matching.py`
- `backend/test_relevant_exp.py` -> `backend/tests/test_relevant_experience.py`
- `backend/test_score_ownership.py` -> `backend/tests/test_score_ownership.py`
- `backend/test_lexical_1215.py` (removed)
- `backend/check_plant_exp.py` (removed)
- `backend/test_top10.py` (removed)
- `backend/test_rrf_rank.py` (removed)
- `backend/test_candidate_1760668444.py` (removed)
- `README.md`
- `backend/requirements.txt` (removed)
- `backend/workstatus.md` (removed)
- `backend/scripts/analyze_db_schema.py` (removed)
- `backend/scripts/audit_db_integrity.py` (removed)
- `backend/scripts/backfill_cvai_cache.py` (removed)
- `backend/scripts/backfill_embeddings.py` (removed)
- `backend/scripts/backfill_required_skills_from_job_profile_desc.py` (removed)
- `backend/scripts/backfill_vacancy_embeddings.py` (removed)
- `backend/scripts/check_mssql_dependencies.sql` (removed)
- `backend/scripts/data_migration/export_mssql_cvai.py` (removed)
- `backend/scripts/data_migration/import_pg_cvai.py` (removed)
- `backend/scripts/generate_mssql_models.py` (removed)
- `backend/scripts/migrate_phase1_inventory.py` (removed)
- `backend/scripts/migrations/mssql/002_drop_cvai_schema.sql` (removed)
- `backend/scripts/run_historical_shadow_validation.py` (removed)
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
