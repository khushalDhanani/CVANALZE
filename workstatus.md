# Work Status

## Last Completed Task
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
