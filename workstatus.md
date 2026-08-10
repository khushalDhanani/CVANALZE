# Work Status

## Last Completed Task
**Restrict candidate vacancy selection to verified matches**

### Architecture Impact Analysis
- Kept deterministic backend scoring authoritative and tightened the existing canonical `VacancyFitEvaluator` instead of adding a second matching engine.
- Both enriched matching and the legacy/basic scoring path now use the same strict eligibility rule.
- Only verified HIGH/MATCHED results without mandatory failures, domain rejection, or invalid hierarchy enter `suitable_openings`.
- Added defensive frontend normalization so previously stored candidate analyses are corrected immediately on `/candidates/[id]`; potential and disqualified vacancies remain visible for HR review.
- No API field, route, Ollama integration, persistence format, or candidate record was removed.

### Files Changed
- `backend/app/services/match_evaluators.py`.
- `backend/app/services/scoring_engine.py`.
- `backend/app/schemas/match.py`.
- `backend/app/schemas/analysis.py`.
- `backend/tests/test_vacancy_match_status.py`.
- `frontend/src/utils/candidateDetail.ts`.
- `frontend/src/app/candidates/[id].tsx`.
- `frontend/src/__tests__/candidateDetailGeneric.test.mjs`.
- `workstatus.md`.

### Implementation
- Stopped promoting `POTENTIAL_MATCH`/MEDIUM vacancies into `suitable_openings`.
- Made mandatory failures and explicit no-strong-match statuses hard disqualifiers even when the numeric score is high.
- Required an explicit verified classification and compatible match status for canonical selection.
- Replaced the legacy scorer's duplicated HIGH-or-MEDIUM list comprehension with `VacancyFitEvaluator.is_eligible_match`.
- Normalized stored detail payloads before rendering.
- Invalid selected vacancies move to `unsuitable_openings`, the best match is recomputed from verified selections, and stale genuine-match flags/statuses are corrected.
- Updated the manual-review explanation and schema descriptions to reflect the stricter contract.

### Verification Checklist
- [x] Audited all 30 stored result files, including local test fixtures.
- [x] Found four currently selected vacancy entries; three satisfy the strict verified-match criteria and one 72.3% MEDIUM entry is demoted to manual review.
- [x] Added backend regression coverage for verified HIGH, MEDIUM/potential, and mandatory-failure cases.
- [x] Added frontend regression coverage confirming only verified HIGH matches remain selected while rejected entries remain reviewable.
- [x] Serena diagnostics found no errors or warnings in the changed frontend files or `scoring_engine.py`.
- [x] The only reported backend diagnostic is the pre-existing `_stop_phrases` return-type warning at `match_evaluators.py:34`, outside the changed selection logic.
- [x] `git diff --check` passed.
- [ ] Builds and tests were not run because repository instructions require an explicit request.

### Refactoring Performed
- Consolidated both backend selection paths on the existing canonical evaluator.
- Added one reusable candidate-detail match normalizer rather than embedding filtering rules in JSX.

## Previous Task
**Make candidate names consistent across directory cards and detail pages**

### Architecture Impact Analysis
- Centralized read-time candidate-name revalidation in the existing deterministic `ResumeFieldExtractor`.
- Both `/candidates/search` and `/candidates/{id}` now normalize names through the same path before mapping their existing response contracts.
- No candidate-specific rule, UI redesign, API field, Ollama integration, or persistence side effect was introduced.

### Files Changed
- `backend/app/services/resume_field_extractor.py`.
- `backend/app/services/candidate_search_service.py`.
- `backend/app/api/candidates.py`.
- `backend/tests/test_candidate_search_flow.py`.
- `backend/tests/test_cv_extraction.py`.
- `workstatus.md`.

### Root Cause and Implementation
- The detail endpoint revalidated stale fallback/invalid names before responding, but the candidate search service returned the persisted `full_name`/`candidate_name` unchanged.
- Stored-result audit identified `cv_gptsuifgr321345678o9p` as `Gtworks` from `email_username_fallback`; this explains why its card could disagree with the corrected detail page.
- The reported `cv_13736_HIRANI` record stores `EDUCATION QUALIFICATION: -` as a high-confidence name while the real name is embedded in a parser-merged `PERSONAL DETAILS NAME: ... PERMANENT ADDRESS: ...` line.
- Moved the generic revalidation from the detail API into `ResumeFieldExtractor.revalidate_candidate_name` and invoked it for every valid list record before field mapping.
- Added generic inline `NAME:` field extraction that stops at adjacent personal-detail labels and rejects owner-qualified labels such as company, institution, father, mother, or spouse names.
- The shared method supports stale fallback, missing, structurally invalid, and parser-merged names using CV text, contact structure, configured extraction rules, and existing confidence gates.

### Verification
- Stored-result audit found two affected completed records: one invalid education-heading name and one email-username fallback; no top-level/contact alias mismatch was found among the remaining stored records.
- Added candidate-search regressions for stale fallback, missing names, and the merged personal-details format that previously produced `EDUCATION QUALIFICATION: -`.
- Added focused extractor coverage confirming the merged structure resolves to the name inside the labeled field rather than the following education heading.
- Focused source tracing confirms both list and detail paths call the same revalidation method.
- `git diff --check` passed.
- Rebuilt and recreated the local API container with the merged local Compose configuration; the API is healthy.
- Live `/api/v1/candidates/search` verification returns `VIRAL D. HIRANI`, `ZALA SAMJUBHA RANUBHA`, and `Tarun Gupta` for the three screenshot records.
- Each corresponding `/api/v1/candidates/{id}` response returns the exact same `full_name` and `candidate_name` as the list response.

### Refactoring Performed
- Removed the detail-endpoint-only name helper and replaced it with one reusable extractor method.

## Previous Task
**Remove confidence badges from candidate directory**

### Architecture Impact Analysis
- Kept the candidate directory route, search API, response types, and detail-page confidence rendering unchanged.
- Removed confidence-tier presentation only from `/candidates`; candidate field values and missing-value fallbacks still use the existing shared component.

### Files Changed
- `frontend/src/app/candidates/index.tsx`.
- `workstatus.md`.

### Root Cause and Implementation
- The list row preferred the legacy top-level `name_confidence_tier` alias over the normalized `field_confidence_tiers.name` value. Those aliases can disagree on older records.
- Removed `nameTier` and the other list-only tier mappings, then stopped passing confidence tiers to every candidate-directory field so no confidence badge is rendered.
- No API contract or candidate detail behavior changed.

### Verification
- Focused source check confirms `/candidates` no longer declares tier variables or passes a `tier` prop to `FieldConfidenceView`.
- `git diff --check` passed.
- Build and test commands were not run, per the repository instruction requiring an explicit request.

### Refactoring Performed
- Removed the four now-unused tier variables from the list-row renderer.

## Previous Task
**Generic CV extraction and candidate-detail audit**

### Architecture Impact Analysis
- Preserved the required `route ID -> API -> extraction/normalization -> typed view model -> dynamic UI` flow.
- Candidate identity remains deterministically extracted; the detail API revalidates legacy invalid/fallback names without candidate-specific rules.
- Frontend normalization remains a single typed boundary and does not infer vacancy data as candidate identity.

### Files Changed
- Backend extraction/API/tests: `backend/app/services/resume_field_extractor.py`, `backend/app/api/candidates.py`, `backend/tests/test_cv_extraction.py`.
- Frontend normalization/UI/tests: `frontend/src/utils/candidateDetail.ts`, `frontend/src/types/api.ts`, `frontend/src/app/candidates/[id].tsx`, `frontend/src/components/ui/ExperienceTimelineCard.tsx`, `frontend/src/__tests__/candidateDetailGeneric.test.mjs`.
- `workstatus.md`.

### Audit Findings and Fixes
- Removed the fixed technology/role regex introduced for one merged header; OCR name/role boundaries now use versioned `job_title_denylist` and `header_denylist` configuration.
- Replaced contact-proximity first-match selection with structural candidate ranking, preventing labels such as education, state, or subject fields from becoming names.
- Revalidates both low-confidence fallback identities and structurally invalid legacy high-confidence identities.
- Removed schema assumptions caused by nullish-coalescing empty strings, first-array-only education/projects, and company-only experience merging.
- Supports top-level, raw resume, and normalized resume fields; record and flat-string arrays; nested certification containers; normalized value objects; multiple roles at one employer; and partial/null payloads.
- Removed timeline array truncation and `N/A`/`Not specified` rendering. Missing timeline data and metadata are hidden rather than synthesized.
- Production code contains no candidate-specific names, IDs, emails, locations, or CV-layout strings.

### Verification
- Backend focused extraction/API tests: 8 passed across ordinary headers, generic-email fallback, filename fallback, two distinct OCR-merged layouts, invalid field labels, and legacy response revalidation.
- Frontend generic mapper test: passed for canonical, normalized, flat, nested, partial, mismatched-ID, and multi-role payloads.
- Existing frontend suites: 20 passed; strict TypeScript compilation passed.
- Python compilation and `git diff --check`: passed.
- Corpus mapper audit: 22 stored candidate payloads across 6 distinct section/contact shapes completed without exceptions or null sentinel leakage.
- Rebuilt API/worker and verified four different stored CV structures end to end:
  - `cv_gptsuifgr321345678o9p` -> `Tarun Gupta`, populated contact, experience, education, skills, and projects.
  - `cv_1761281901_CandidateCVFileName_13595` -> `Shubham Sureshbhai Gavhane`, missing phone/location/projects handled as absent.
  - `cv_13736_HIRANI` -> `Viral D. HIRANI`, previously invalid education-heading identity corrected.
  - `cv_1760681936` -> `ZALA SAMJUBHA RANUBHA`, letter-style resume and previously invalid state/subject identities corrected.

### Refactoring Performed
- Consolidated configured role-boundary detection, structural name scoring, and invalid-label rejection in the existing extractor.
- Consolidated multi-source field precedence, cleaning, merging, and deduplication in the typed frontend view-model mapper.
- No new extractor/client/API route was introduced; no Ollama, scoring, or visual-design behavior changed.

## Previous Task

**Recover local API from startup failure**

### Architecture Impact Analysis
- No application code or security control changed.
- The failure came from launching only the production Compose definition on a local machine, which omitted the documented local override.

### Files Changed
- `workstatus.md` only.

### Implementation and Verification
- Confirmed `verify_mssql_readonly()` was terminating production-mode startup because the configured MSSQL account has write permissions.
- Confirmed the API-key message was a separate warning, not the terminating exception.
- Recreated the stack with `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d pgvector redis api worker`.
- API, worker, PostgreSQL, and Redis are healthy.
- `GET /` returns the CV Analyzer welcome response.
- `GET /api/v1/candidates/cv_gptsuifgr321345678o9p` returns HTTP 200 with the exact `id`/`scan_id`, `Tarun Gupta`, and `COMPLETED` status.

### Refactoring Performed
- None.

## Previous Task

**Dynamic candidate CV detail page audit and repair**

### Architecture Impact Analysis
- Preserved the generic `/candidates/[id]` route and existing `/api/v1/candidates/{candidate_id}` contract.
- Added one frontend normalization boundary between the verified API schema and rendering; no candidate-specific UI logic or mock data was introduced.
- Kept deterministic resume extraction authoritative and added a generic read-time upgrade for legacy results whose names were stored from low-confidence email/filename fallbacks.

### Root Cause
- Route resolution and API lookup selected the correct result for `cv_gptsuifgr321345678o9p`; `id` and `scan_id` both matched the requested route.
- The stored result was wrong: Docling merged the PDF header into `OW T A R U N GUPTAFULL STACK D E V E L O P E R...`, so name extraction fell back to the email username and persisted `Gtworks` even though the CV contains `TARUN GUPTA`.
- The page independently caused incomplete/misleading output by using a vacancy title as a candidate-title fallback, mapping only selected raw fields, truncating education/certifications/experience, omitting projects and responsibilities, rendering placeholder rows, and accepting stale out-of-order requests after route changes.

### Files Changed
- `backend/app/services/resume_field_extractor.py`: recovers names from parser-merged, letter-spaced header/name/job-title lines.
- `backend/app/api/candidates.py`: upgrades stale low-confidence fallback names with the current deterministic extractor before returning candidate details.
- `backend/tests/test_cv_extraction.py`: covers merged-header extraction and detail-response stale-name upgrades.
- `frontend/src/utils/candidateDetail.ts`: verified response normalization, route/response identity validation, null cleanup, entity decoding, source merging, and complete section view models.
- `frontend/src/types/api.ts`: additive candidate-detail response types matching the observed API payload.
- `frontend/src/app/candidates/[id].tsx`: route-safe loading and fully dynamic rendering for all existing CV sections.

### Dynamic Behavior Implemented
- Normalizes and validates `string | string[]` route IDs, rejects path-like/empty IDs, verifies response identity, and reports invalid, empty, mismatched, and failed responses.
- Clears candidate and recommendation state on every route change and sequence-guards all asynchronous responses to prevent another candidate's data from flashing or overwriting the current route.
- Dynamically renders all experience entries and responsibilities, education entries, certifications, skills, projects, contact links, summary, extracted text, and existing analysis arrays.
- Hides missing sections/rows and removes `null`, `undefined`, `Unknown`, `Not specified`, and fabricated candidate-title/company/vacancy fallbacks.
- Uses candidate work history for candidate title/company fallback and never uses `match_analysis.best_match.job_title` as candidate identity.

### Verification
- `npx tsc --noEmit`: passed with zero TypeScript errors.
- Focused extraction/API tests: 5 passed (`deterministic_name_extraction` and stale-name detail upgrade).
- Python syntax compilation for both changed backend modules: passed.
- Rebuilt Docker `api` and `worker` images and started Redis/PostgreSQL dependencies.
- Route-handler verification in the rebuilt API image:
  - `cv_gptsuifgr321345678o9p` resolved to the exact requested `id`/`scan_id`, returned `Tarun Gupta` from `header_contact_section`, 2 experience records, 2 education records, 21 API skills, and 10 projects.
  - `cv_1761281901_CandidateCVFileName_13595` resolved to the exact requested `id`/`scan_id`, returned `Shubham Sureshbhai Gavhane`, 2 experience records, 11 education records, 25 skills, and no projects; null phone/location remain hidden by the UI mapper.
- Frontend mapper verification rendered 2 roles and 12 responsibilities, 2 education entries, 24 merged skills, and all 10 projects for the requested candidate; the second candidate omitted its absent contact/project fields without leaking null sentinels.
- `git diff --check`: passed.

### Pending Environment Issue
- The HTTP API container currently fails its existing startup safety gate because the configured MSSQL credential has write permissions. The read-only credential must be corrected before browser-level HTTP verification; this security control was not weakened.
- A broader generation-consistency suite had 6 environment failures because host tests resolve PostgreSQL as Docker hostname `pgvector`; 4 tests passed. These failures are unrelated to the candidate-page changes.

### Refactoring Performed
- Consolidated candidate response cleanup and field precedence in one reusable frontend mapper instead of duplicating optional/fallback logic across JSX.
- No Ollama integration, scoring rule, API contract, or visual styling was changed.

## Previous Task

**Local LLM reliability, safety, quality, and observability foundation**

### Architecture Impact Analysis
- Preserved the centralized `OllamaTransport`, `OllamaLLMService`, `EmbeddingService`, versioned cache, hybrid retrieval, and deterministic scoring boundaries.
- Added privacy-safe persistent execution lineage, additive metrics, circuit breaking, resident-model reuse, prompt/data isolation, token-aware context packing, source grounding, retrieval provenance, and shadow confidence metadata.
- Deterministic scores, mandatory gates, and existing API contracts remain authoritative; new response fields are optional/additive.

### Files Changed
- Transport/config/lifecycle: `backend/app/core/config.py`, `backend/app/core/lifecycle.py`, `backend/app/core/request_context.py`, `backend/app/services/ollama_transport.py`, `docker-compose.yml`, `docker-compose.local.yml`.
- Tracing/cache/metrics: `backend/app/models/llm_trace.py`, `backend/app/repositories/llm_trace.py`, `backend/app/repositories/llm_cache.py`, `backend/app/schemas/llm_trace.py`, `backend/app/services/quality_metrics.py`, `backend/app/services/performance_service.py`, migration 021 and its rollback.
- Quality/security/context: `backend/app/services/llm_input_security.py`, `backend/app/services/context_packer.py`, `backend/app/services/llm_grounding_service.py`, `backend/app/services/confidence_calibration.py`, prompt builders, analysis schemas, `match_service.py`, `vacancy_prefilter.py`, and `shadow_validation_service.py`.
- Evaluation/tests: versioned reliability and confidence artifacts, offline evaluation runner/script, `test_llm_reliability_hardening.py`, transport tests, cache privacy tests, and context-integrity tests.

### Implementation Decisions
- Raw prompts, raw model responses, CV text, and hidden reasoning are no longer serialized into long-lived LLM cache entries or execution traces.
- `done_reason=length` is rejected; bounded deterministic JSON extraction handles fences/trailing output, and Pydantic remains the semantic schema authority.
- Unsupported skills/evidence and unknown vacancy IDs are removed before LLM enrichment is applied. Deterministic matching remains usable on any LLM failure.
- Models remain resident for the configured keep-alive window and unload on shutdown; circuit breaking applies only to transient transport/HTTP failures.
- Hugging Face and Docling caches are persistent Docker volumes. Retrieval ordering now has deterministic tie-breaks and records lexical/vector provenance.
- Confidence calibration uses a versioned shadow-only isotonic artifact. The baseline is identity-mapped until fitted on approved HR-reviewed outcomes.
- No general-purpose LLM tool gateway or conversational memory was introduced because no concrete authorized workflow currently requires either.

### Verification
- `python3 -m pytest tests/test_cv_extraction_integrity.py tests/test_llm_domain_validation.py tests/test_llm_reliability_hardening.py tests/test_phase5_ollama_standardization.py -q`: **45 passed**.
- Offline reliability evaluation: **4/4 deterministic gates passed** for injection detection, de-identification, long-context retention, and counterfactual invariance.
- Python compile check for the application and affected tests: **passed** using a sandbox-safe bytecode cache.
- Merged Docker Compose configuration validation: **passed**.
- A broader local suite could not collect Docling-dependent API tests because Docling is not installed in the host Python environment; DB-dependent retrieval tests also require the running PostgreSQL service.

### Pending Rollout Work
- Apply PostgreSQL migration 021 before enabling durable trace persistence in a deployed environment.
- Run the live-Ollama warm/cold benchmark, golden retrieval/ranking evaluation, approved fairness slices, and representative shadow cycle before enforcing new quality gates.
- Fit and approve the confidence calibration artifact using access-controlled HR-reviewed outcomes.
- Migration application, service restart, and production/shadow activation were intentionally not performed in this implementation task.

### Refactoring Performed
- Removed the duplicate `MATCHING_VERSION` setting and retained `2.1.0` as the single authoritative value.
- Fixed shadow-validation recursion by marking internal shadow runs.
- Reused the existing centralized Ollama and embedding integrations; no duplicate client, retry loop, cache, or generation wrapper was introduced.

## Previous Task

**CV extraction and maintenance-opening scoring fixes: restart, reprocess, and verification**

### Architecture Impact Analysis
- Preserved the existing extraction, taxonomy evaluation, scoring, API, and RQ worker architecture.
- Reused the centralized CV reprocess endpoint and existing processing queue; no API contracts or Ollama integrations were added or changed.
- Rebuilt both `api` and `worker` because backend source is copied into their Docker images and scoring executes in the worker.

### Files Modified
- `backend/app/services/resume_field_extractor.py`: strips/rejects field-label prefixes such as `Duration:` when deriving job titles.
- `backend/app/services/match_evaluators.py`: recognizes named department sub-teams as the same root family.
- `backend/app/services/scoring_engine.py`: supports sparse-CV maintenance skill matching and promotes eligible MEDIUM matches to `suitable_openings`.
- `workstatus.md`: recorded deployment and end-to-end verification evidence.

### Implementation and Operations
- The three service files passed the previously completed syntax check.
- Rebuilt and recreated the local Docker `api` and `worker` services with the completed fixes.
- Forced reprocessing of `cv_1761281901_CandidateCVFileName_13595` through `POST /api/candidates/{candidate_id}/reprocess`.
- The first RQ attempt timed out after 300 seconds while populating a cold 570 MB Hugging Face/Docling cache; the configured retry ran automatically and completed on attempt 2 of 3.

### Verification Checklist
- [x] API container is healthy and `GET /` returns HTTP 200.
- [x] Worker container is healthy with the RQ scheduler enabled.
- [x] Reprocess job completed with outcome `REPROCESSED`, progress 100, and no terminal error.
- [x] Persisted result is `COMPLETED` at generation sequence 10.
- [x] Candidate resolved as `Shubham Sureshbhai Gavhane`, domain `Industrial Maintenance`, family `Maintenance Team`.
- [x] Work-history titles are `Fitter Executive` and `Fitter Executive (Apprentice)`; neither contains the invalid `Duration:` label.
- [x] Vacancy 1038 (`Executive (Maintenance)`) is suitable: HIGH, 86.4%, no mandatory failures, no domain mismatch cap.
- [x] Vacancy 811 (`Plant Assistant - I (Maintenance)`) is suitable: MEDIUM, 72.3%, `Maintenance Work` satisfied, no mandatory failures, no domain mismatch cap.
- [x] A different 52.3% MEDIUM vacancy with a seniority mandatory failure remains unsuitable, confirming hard gates are preserved.
- [x] Cross-domain Production, C & I, Environment, QA, and Store openings remain capped/unsuitable.

### Pending Work
- None for this task.

### Refactoring Performed
- No additional refactoring was performed during restart and verification.

## Previous Tasks
**Fix Active Vacancies "Unavailable / Failed to fetch directory"**

### Root Cause
`GET /api/jobs` timed out (duration_ms=803,565 — 13+ minutes) because
`EmbeddingSyncService.sync_vacancy_embeddings()` was called **synchronously** inside
`JobRepository.get_all_jobs()` on every cache miss. This blocked the API request thread
while making individual Ollama `nomic-embed-text` embedding calls for all 107 vacancies
sequentially (~700–800 ms each).

The three previously proposed fixes (staleness predicate alignment, fast taxonomy
resolution via `DepartmentNormalizer`/`department_domain_repository`, and
`TaxonomyClassifier` dept-domain fallback) were already applied in a prior session.

### Fix
- **File changed**: `backend/app/repositories/job.py` (lines 183–192)
- Moved `EmbeddingSyncService.sync_vacancy_embeddings(job_dicts_to_return)` from
  a blocking synchronous call to a background `daemon=True` thread named
  `"vacancy-embedding-sync"`.
- The API response is now returned immediately after caching the vacancy list.
  Embedding population proceeds asynchronously without blocking.

### Verification
`GET /api/jobs` was blocking for 70–100+ seconds because `JobPreprocessor.preprocess_job_dicts`
called `TaxonomyClassifier.classify_vacancy` → `DynamicTaxonomyService.resolve_vacancy_domain_and_family`
→ `_resolve_postgres_vector` → `EmbeddingService.generate_embedding` (Ollama HTTP call) for each vacancy
that didn't keyword-match the in-memory matchers (~700ms each × dozens of vacancies).
The frontend's 60s timeout caused "Failed to fetch directory".

### Fix
1. **`dynamic_taxonomy_service.py`**: Added `skip_vector: bool = False` parameter to `resolve_vacancy_domain_and_family`. When `True`, the `_resolve_postgres_vector` (Ollama) call is bypassed entirely.
2. **`job_taxonomy.py`**: Threaded `skip_vector` through `classify_vacancy_dto` and `classify_vacancy`.
3. **`job_preprocessor.py`**: `preprocess_job` now calls `TaxonomyClassifier.classify_vacancy(job, skip_vector=True)`, eliminating all Ollama calls during bulk vacancy loading.
4. **`repositories/job.py`**: Raised `_STALENESS_TTL` from 10s to 30s to better buffer concurrent requests.

### Verification
- **First request**: `GET /api/jobs` → HTTP 200 in **0.94s** (vs previous 70–100s timeout).
- **Second request**: `GET /api/jobs` → HTTP 200 in **0.74s** with `CACHE HIT` confirmed in logs.
- No regression: existing taxonomy classification for CV matching still uses vector search (default `skip_vector=False`).

## Previous Tasks
**Fix worker processing failures (prompt templates, DepartmentDomainMaster, RQ retries)**
- Seeded prompt templates, DepartmentDomainMaster (52 rows), fixed RQ scheduler.

**Fix `relation "cv_results" does not exist`**
- `INITIALIZE_DATABASE_ON_STARTUP` set to `"true"`.

**Fix Docker stack not starting locally**
- Migration fixes, RedisCache bug fix, rule-config profile seeded.

**Home Page Card Overlap & Layout Fix**
- Responsive grids, eliminated h-full collisions, integrated StatusBanner components.


### Root Cause
The worker log showed three distinct failures during CV processing:
1. `relation "cvai.prompt_templates" does not exist` -> `PromptService.get_prompt` raises
   `PROMPT_UNAVAILABLE` when no template row exists. The table was created by `create_all`
   (after the `INITIALIZE_DATABASE_ON_STARTUP` fix) but contained **0 rows**.
2. `column DepartmentDomainMaster.DepartmentNameSnapshot does not exist` -> migration 005
   created the table without that column; `create_all` skips existing tables, so the drift
   persisted. Also `DepartmentDomainMaster` and `department_alias_mappings` were empty.
3. RQ retries were never executed: the worker ran without `--with-scheduler`, so jobs placed
   in the `rq:scheduled:*` zset by `retry_intervals` sat forever.

### Fix
- Seeded prompt templates via `backend/scripts/seed_prompts.py` (one-off api container):
  `dynamic_mapping`, `match_analysis`, `optimized_match`, `profile_extraction`,
  `work_experience_extraction_v1` (all `language=en`, `environment=production`, active).
- New migration `020_add_department_name_snapshot.sql` (+ down) adds
  `"DepartmentNameSnapshot" VARCHAR(200)` to `public."DepartmentDomainMaster"`; applied.
- Seeded `DepartmentDomainMaster` (52 rows) from `app/data/department_domains_seed.json`
  via `backend/scripts/seed_department_domains.py`.
- Manually requeued the stuck job `cvjob_0c22fc0786d40c9399263854c08a49b5ac29d9fb1fab2122834c5c754794c403-2`.
- Added `--with-scheduler` to the `worker` command in both `docker-compose.yml` and
  `docker-compose.local.yml`; recreated the worker container.

### Verification
- Failed job re-processed: `Successfully completed process_cv_job(...)`, `Job OK`, status `finished`.
- `public.cv_results` row persisted: `cv_ut1765894215` / `Utkarsh Patil` / `COMPLETED` / `generation_sequence=2`.
- `optimized_match` Ollama call succeeded (after an initial timeout fell back to retry and completed).
- Worker now healthy with scheduler: `rq worker --with-scheduler ...`.
- API healthy: `GET /` -> 200, `GET /api/config/active` -> version 1.1.0.

## Previous Tasks
**Fix `relation "cv_results" does not exist` (missing public-schema model tables)**
- `docker-compose.local.yml`: `INITIALIZE_DATABASE_ON_STARTUP` `"false"` -> `"true"`; missing model tables created by `create_all`.

## Previous Tasks
**Fix Docker stack not starting locally**
- Migration 018 schema-qualification fix, new migration 019 (`system_rules.target_value` -> TEXT),
  stale `--dialect postgres` flag removal, `RedisCache._get_client()` bug fix,
  seeded/activated rule-config profile v1.1.0 from `tests/mock_rule_config.py`.

## Older Tasks
**Home Page Card Overlap & Layout Fix**

### Key Fixes & Architecture Updates

1. **Eliminated `h-full` Height Collisions**:
   - Removed `className="h-full"` from all `<DenseRow>` instances across Quick Workflows, Recent Activity, Top Vacancies, and System Health. This eliminates the height stretching and overlapping when flex items wrap on mobile or intermediate screen widths.

2. **Responsive Stat & Action Grids**:
   - Wrapped top summary statistics and Needs Attention cards in `<ResponsiveStatGrid>`.
   - Wrapped Quick Workflows, Recent Activity, Top Vacancies, and System Health rows in `<ResponsiveFieldGrid minItemWidth={280} gap={10}>`.

3. **Status Banners**:
   - Integrated `<StatusBanner>` for error messaging in Recent Activity and Vacancy Directory loading failures.

### Verification
- **TypeScript Compilation (`npx tsc --noEmit`)**: **PASSED (0 errors)**.
