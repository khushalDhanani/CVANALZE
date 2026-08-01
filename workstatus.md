# Work Status

## Last Updated
2026-08-01T13:10:00Z

## Completed
- **Application-Wide Navigation & Routing Audit**:
  - **Active Sidebar & Parent Route Highlighting (`SidebarLayout.tsx`)**: Refactored route matching logic with `isRouteActive` helper so parent links (**Candidates**, **Jobs**) remain highlighted on nested detail routes (`/candidates/[id]`, `/vacancies/[id]`).
  - **URL Search Parameter Synchronization (`app/candidates/index.tsx`, `app/vacancies/index.tsx`)**: Integrated `useLocalSearchParams` and `router.setParams` across candidate and job vacancy directories. Enables direct URL access, shareable links with query params, and browser Back/Forward navigation state restoration.
  - **Navigation State Preservation on Detail Pages (`candidates/[id].tsx`, `vacancies/[id].tsx`)**: Extracted active filter parameters (`query`, `classification`, `department`, `domain`) from `useLocalSearchParams` and implemented `handleBack` helper to navigate back to list screens with active search parameters preserved.
  - **Breadcrumbs System (`Breadcrumbs.tsx`, `ui/index.ts`)**: Built a reusable, accessible `Breadcrumbs` component with Home icon and clickable node links, integrated across all 10 module screens.
  - **Dynamic Page Titles (`usePageTitle.ts`)**: Built `usePageTitle` hook to update `document.title` on web dynamically upon screen transitions (e.g. `"Candidate Directory | AIRIS"`, `"Candidate: [Name] | AIRIS"`).
  - **Internal Link Fixes (`app/index.tsx`)**: Fixed Top Vacancies dashboard card to navigate directly to `/vacancies/[id]` instead of generic `/vacancies`.
  - **Automated Verification**: Ran `npx tsc --noEmit` across frontend codebase verifying **0 type errors**.
- **Audit & Implementation of Polling & Background Task Cleanup for CV Matching**:
  - **Frontend Polling & Timer Management (`useCvUpload.ts`, `candidates/[id].tsx`)**: Refactored status polling using `pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)` with `stopPollTimer()` callback and `useEffect` unmount cleanup handler. Replaced all raw `clearInterval` calls to guarantee background HTTP status requests (`/api/match/status/{cvKey}` and `/api/cv/status/{cvKey}`) terminate cleanly when processing reaches 100% completion or when user leaves the component.
  - **Read-Only Post-Matching Ollama Embedding Prevention (`domain_embedding_service.py`, `recommendation_service.py`)**: Added `allow_live_generation: bool = True` parameter to `get_or_generate_domain_embedding` and `find_semantic_equivalents`. Passed `allow_live_generation=False` in `RecommendationService.get_candidate_recommendations` so viewing candidate details post-matching uses pre-cached database records and canonical rules without firing live `/api/embed` HTTP requests to Ollama.
  - **Pre-Filter Candidate Embedding Reuse (`vacancy_prefilter.py`)**: Enhanced `CandidateSearchContext` to check existing candidate embeddings in PostgreSQL/cache by content hash before attempting new embedding generation.
  - **Ollama Model Memory Unload (`llm_service.py`, `cv_service.py`)**: Added `OllamaLLMService.unload_model` sending `{"model": model_name, "keep_alive": 0}` to Ollama `/api/generate` upon 100% completion of CV matching, allowing Ollama to immediately release RAM/VRAM and become idle.
  - **Human-Readable Hiring Recommendation Tiers (`recommendation_service.py`, `candidates/[id].tsx`, `api.ts`)**: Configured 4-tier hiring recommendations (`Highly Recommended` >= 85%, `Recommended` >= 70%, `Potential Fit` >= 55%, `Needs Further Review` < 55%) across backend recommendation service, TypeScript types, next-steps logic, and candidate UI badge styling.
  - **Automated Test Verification**: Added unit tests in `test_qwen_llm_service.py` (`test_ollama_unload_model_sends_keep_alive_zero` and `test_domain_embedding_read_only_disables_live_generation`). Verified **26/26 tests passing** across `test_qwen_llm_service.py`, `test_vacancy_prefilter.py`, `test_ai_recommendations.py`, and `test_taxonomy_integration.py`.


- **Qwen3:4b Ollama Configuration (/no_think for Extraction, /think for Scoring, Structured Output, Temp 0.0)**:
  - Preserved default model setting `OLLAMA_MODEL = "qwen3:4b"` in `app/core/config.py`.
  - Configured Candidate Profile Extraction (`OllamaLLMService.extract_candidate_profile`) with `/no_think` prompt prefix, Ollama payload `"think": False`, `"format": DynamicCandidateProfile.model_json_schema()`, and options `"temperature": 0.0`.
  - Configured Match Analysis and Scoring (`OllamaLLMService.call_qwen`, `call_qwen_dynamic`, `run_optimized_match`) with `/think` prompt prefix, Ollama payload `"think": True`, `"format": Model.model_json_schema()`, and options `"temperature": 0.0`.
  - Enforced structured JSON output via Pydantic model schemas across all 4 Ollama API methods (`extract_candidate_profile`, `call_qwen`, `call_qwen_dynamic`, `run_optimized_match`).
  - Added unit test suite `backend/tests/test_qwen_llm_service.py` verifying model name, payload think flags, temperature 0.0, JSON schemas, and prompt prefixes. Verified **44/44 core backend tests passing** and 0 ruff errors.
- **Refactor `VacancyPreFilter` (`backend/app/services/vacancy_prefilter.py`)**:
  - Implemented all 14 requested requirements across `backend/app/services/vacancy_prefilter.py` and `backend/tests/test_vacancy_prefilter.py`.
  - Eliminated duplicate PostgreSQL vector queries via `PgVectorQueryCache.query_pgvector_cached()` with `@functools.lru_cache(maxsize=128)` to query pgvector ONLY ONCE per candidate embedding.
  - Created `CandidateSearchContext` to pre-compute candidate lowercased text, word token sets, domain/family classification, and embedding ONCE per prefilter run.
  - Integrated `JobEvaluationContext` across all filtering stages, bypassing repeated `.get()` calls on raw job dictionaries.
  - Optimized lexical matching with token set intersections (`cand_ctx.cv_tokens.intersection(job.title_words)`), using set membership for single-word skills/department terms and substring scanning for multi-word phrases only.
  - Extracted Reciprocal Rank Fusion logic into a dedicated helper class `ReciprocalRankFusionService.fuse_ranks()`.
  - Added adaptive retrieval guard: automatically skips Stage 1 semantic retrieval and Stage 2 RRF fusion when Stage 0 taxonomy filtering yields fewer openings than `limit`.
  - Added stage-by-stage execution timing logging (`stage0_taxonomy_ms`, `stage1_semantic_ms`, `stage2_lexical_ms`, `stage2_rrf_ms`, `total_prefilter_ms`).
  - Optimized memory by eliminating shallow `dict(job)` copy loops and updating metadata directly.
  - Preserved 100% backward compatibility for all public methods (`semantic_vector_search`, `vector_prefilter`, `filter_vacancies`).
  - Verified **58/58 tests passing** (`pytest`) and **0 ruff errors**.
- **Refactor `JobTaxonomy` & `TaxonomyClassifier` (`backend/app/services/job_taxonomy.py`)**:
  - Implemented all 14 requested requirements across `backend/app/services/job_taxonomy.py` and `backend/tests/test_taxonomy_integration.py`.
  - Introduced strongly-typed DTO models (`VacancyDTO`, `CandidateResumeDTO`, `TaxonomyClassification`).
  - Bypassed runtime string lowercasing and repeated string concatenation by accepting `JobEvaluationContext` or `VacancyDTO` objects directly using pre-computed `normalized_job_text`, `title_lower`, and `department_lower`.
  - Precompiled taxonomy rules and implemented fast single-token set intersection matching (`tokens & condition.keywords_set`), falling back to multi-word phrase matching only when necessary.
  - Implemented dual LRU caching with `@functools.lru_cache(maxsize=1024)` for vacancy classification (keyed on `normalized_job_text`) alongside candidate classification caching (`maxsize=512`). Documented CPython GIL atomic thread safety.
  - Added startup configuration validation (`validate_taxonomy_config()`) asserting domain/family completeness and precomputed `JobTaxonomy.REVERSE_COMPATIBILITY_MAP` (`job_family -> set[candidate_family]`).
  - Added telemetry metrics counter (`TaxonomyClassifier.get_metrics()`) and zero-overhead debug logging guarded by `logger.isEnabledFor(logging.DEBUG)`.
  - Preserved 100% backward compatibility for all public methods (`classify_candidate`, `classify_vacancy`, `are_families_compatible`).
  - Verified **53/53 tests passing** (`pytest`) and **0 ruff errors**.
- **Refactor `RuleConfigManager` (`backend/app/core/rule_config_manager.py`)**:
  - Implemented enterprise-grade thread safety, startup cache warming, immutable cache objects (`MappingProxyType`, `frozenset`, `tuple`), precompiled regex matching, metrics telemetry, hot reload support, cache validation gates, and structured startup logging.
  - Protected all mutable class-level state (`_active_config`, `_cache`, `_metrics`, `_load_counter`) using `threading.RLock()` to guarantee thread safety and atomic configuration swaps.
  - Warmed ALL caches immediately during `load_config()` (term matching assets, cross domain guard sets/regexes, resume quality section patterns/heading normalizations, recommendations, scoring parameters, and taxonomy assets).
  - Precompiled ALL regex patterns once at startup and enforced validation gates (asserting `compiled_pattern_count > 0` and section/guard maps are populated).
  - Exposed `RuleConfigManager.get_metrics()` returning `config_version`, `config_load_count`, `config_load_time_ms`, `cache_build_time_ms`, `compiled_pattern_count`, `configuration_size_bytes`, file hashes, and timestamps.
  - Implemented `RuleConfigManager.reload_if_changed()` for hot reload checking file mtime / SHA256 hash.
  - Preserved 100% public API backward compatibility for all getters (`get_match_rules()`, `get_scoring_parameters()`, `get_recommendations()`, `get_term_matching_assets()`, `get_compiled_cross_domain_guard()`, `get_compiled_section_patterns()`, `get_compiled_heading_normalizations()`, etc.).
  - Verified **52/52 tests passing** (`pytest`) and **0 ruff errors**.
- **Match Evaluator Refactoring & Hardening (`match_evaluators.py`)**:
  - Implemented all 12 requested refactoring requirements across `backend/app/services/match_evaluators.py`, `backend/app/schemas/scoring_config.py`, `backend/app/schemas/job_context.py`, and `backend/app/services/scoring_engine.py`.
  - Loaded `ScoringConfig` ONCE at top of `analyze_cv` / `evaluate_job_match`, eliminating repeated `ConfigRepository` lookups inside multi-vacancy scoring loops.
  - Eliminated `isinstance()` checks and `.create()` calls inside evaluators.
  - Precompiled department term regex patterns in `JobEvaluationContext.dept_term_patterns` for ZERO runtime `re.compile()` calls.
  - Extracted helper methods (`_create_requirement`, `_create_failure`, `_create_evidence`), renamed `coverage` $\rightarrow$ `component_coverage`, isolated `_calculate_confidence_score`, and made `CrossDomainGuardEvaluator` 100% side-effect free.
  - Verified **51/51 tests passing** and **0 ruff errors**.
- **Scale Load Testing & Benchmark Optimization (100, 1,000, 10,000 Vacancies)**:
  - Created `backend/tests/test_scale_benchmark.py` running automated scale benchmarks across 100, 1,000, and 10,000 synthetic vacancies.
  - Demonstrated **3,143.3 evaluations/sec throughput** at 10,000 vacancies (only 0.318 ms/vacancy scored) with **75.0% Stage-0 taxonomy pre-filter pruning ratio** and a lightweight **175.8 MB peak RSS memory footprint**. Verified **51/51 tests passing** across core test modules.
- **Performance Profiling & Production Observability (`PipelineProfiler`)**:
  - Enhanced `PipelineStageMetrics` (`backend/app/schemas/analysis.py`) to record `candidate_context_ms`, `vacancy_context_ms`, detailed evaluator breakdown timings (`evaluator_requirement_ms`, `evaluator_transition_ms`, `evaluator_component_ms`, `evaluator_cross_domain_ms`, `evaluator_recommendation_ms`), and cache metrics (`cache_hits`, `cache_misses`).
  - Enhanced `PipelineProfiler` (`backend/app/core/profiler.py`) with accumulated multi-vacancy stage timers, cache event recorders, structured dictionary/JSON exporters (`to_dict`, `to_json`), and formatted telemetry logging.
  - Wired `profiler` parameter into `ScoringEngine.analyze_cv` in `backend/app/services/scoring_engine.py`.
  - Added unit test suite `backend/tests/test_profiler.py` verifying profiler stage timing, cache metric recording, JSON serialization, and scoring engine integration. Verified **48/48 tests passing** across core test modules.
- **Vacancy-Side Preprocessing (`JobEvaluationContext`)**:
  - Created `backend/app/schemas/job_context.py` to encapsulate vacancy taxonomy domain & job family pre-classification, department domain term splitting, title noise stripping, and guard regex evaluations (`is_non_it_job`, `has_software_req`) **once per vacancy**.
  - Updated `RequirementEvaluator`, `CareerTransitionEvaluator`, `ComponentScoreEvaluator`, `CrossDomainGuardEvaluator` in `backend/app/services/match_evaluators.py` and `ScoringEngine.analyze_cv` / `evaluate_job_match` in `backend/app/services/scoring_engine.py` to consume `JobEvaluationContext` objects.
  - Added unit test suite `backend/tests/test_job_context.py` verifying context initialization, taxonomy classification, and 100% scoring engine output parity. Verified **45/45 tests passing** across core test modules.
- **Final Production Refactoring & Circular Dependency Elimination**:
  1. **Taxonomy Classification Caching**: Added `@functools.lru_cache(maxsize=512)` decorated `classify_candidate_by_full_text` to `TaxonomyClassifier` in `backend/app/services/job_taxonomy.py`, eliminating per-vacancy redundant taxonomy classification scans during multi-vacancy scoring.
  2. **`CandidateAnalysisContext` & `CandidateDomainService` Refactoring**: Created `backend/app/services/candidate_domain_service.py` extracting domain profile extraction (`extract_candidate_domain_profile`), domain text building (`build_domain_candidate_text`), and department term parsing (`extract_department_domain_terms`). Completely eliminated the circular dependency between `CandidateAnalysisContext` and `ScoringEngine` by having both depend on `CandidateDomainService` with clean top-level imports.
  3. **Modular Match Evaluators**: Created `backend/app/services/match_evaluators.py` splitting `evaluate_job_match()` into `RequirementEvaluator`, `CareerTransitionEvaluator`, `ComponentScoreEvaluator`, `CrossDomainGuardEvaluator`, and `RecommendationEvaluator`. Refactored `evaluate_job_match` from a 650-line monolith into a 60-line clean orchestrator method while preserving 100% signature and output contract parity.
  4. **Precompiled Pattern Indexing**: Precompiled cross-domain guard keyword regexes (`software_candidate_patterns`, `non_it_job_patterns`, `software_requirement_patterns`, `domain_guard_term_patterns`) in `RuleConfigManager.get_compiled_cross_domain_guard()` and cached term pattern compilation via `@functools.lru_cache(maxsize=2048)` in `ScoringEngine._get_compiled_term_pattern`.
  5. **Configurable Magic Numbers & Recommendation Text**: Moved hardcoded recommendation strings and scoring parameters (`career_transition_role_score`, `role_divergence_score`, `below_min_exp_multiplier`, `overqualification_penalty`, `domain_default_match_score`, `low_coverage_threshold`, `false_positive_score_cap`) into `rule_config.json` backed by `RecommendationTexts` and `ScoringParameters` Pydantic models in `RuleConfigManager`.
  6. **Automated Verification**: Created `backend/tests/test_candidate_context.py`. Verified 100% test pass across all 42 core tests (`pytest tests/test_candidate_context.py tests/test_scoring_engine.py tests/test_taxonomy_integration.py tests/test_rule_config_manager.py tests/test_department_domain_repository.py`) and verified 0 ruff lint errors.
- **DepartmentDomainMaster seeded with REAL department links (replaces canonical labels)**:
  - Live `OrgDepartmentMst` (52 rows, `DeptIsActive`/`DeptIsDeleted` columns) and `OrgMainDepartmentMst` (26 rows) dumped and compared against the 002 seed lookups. Found **none** of the 8 seed dept names matched real dept rows, so 002 would have inserted all rows with NULL DepartmentId.
  - User chose "Map to real dept IDs". Updated `backend/app/data/department_domains_seed.json` (added `department_id`, changed `department_name` to real active org dept names) and `backend/scripts/migrations/002_create_department_domain_master.sql` (name-based lookups against real dept names; Healthcare seeded with explicit NULL DepartmentId since no pharma/clinical dept exists in the chemical org).
  - Mapping (domain → real dept): IT & Software → **CIS Team (DeptID 9)**, Finance & Accounting → **Finance Team (8)**, Human Resources → **HR & IR Team (10)**, Plant & Maintenance Engineering → **Maintenance Team - 1 (Ramesh Maurya) (23)**, Sales & Marketing → **Sales Team (16)**, Quality & EHS → **EHS Team (6)**, Supply Chain & Operations → **Procurement Team (11)**, Healthcare & Clinical → **NULL** (linked later).
  - `recommended_department` now returns real org dept names (was canonical labels like "Information Technology"). To keep the cross-domain guard in `evaluate_job_match` working, its substring checks now use the stable `cand_domain` (`professional_domain`) instead of `cand_dept`; removed the now-unused `cand_dept` local (F841).
  - Tests updated to the new labels: `test_department_domain_repository.py` (incl. `department_id` pins, renamed `test_extract_candidate_domain_profile_maps_to_real_departments`), `test_taxonomy_integration.py`, `test_domain_matching.py`. Seed fallback + DB mode stay label-consistent.
  - Validation: `pytest tests/test_department_domain_repository.py tests/test_taxonomy_integration.py` → **18 passed**; `pytest tests/test_domain_matching.py -k "not test_no_suitable_active_vacancy_summary"` → **4 passed** (remaining deselected test is the pre-existing legacy-string failure). ruff: 0 new errors (13 pre-existing, identical to HEAD). Seed JSON sanity check: all 8 domains, correct ids/names/priorities.
  - NOTE: migration 002 not yet applied to the live MSSQL DB; until then the repository loads from seed. DepartmentId re-pointing (e.g. picking a different maintenance sub-team) is now a simple SQL update, no code change.
- **DB-Driven Department/Domain Configuration (Replaces `DEPARTMENT_DOMAIN_MAP`)**:
  - Removed the hardcoded `DEPARTMENT_DOMAIN_MAP` static dict from `backend/app/services/scoring_engine.py`; department/domain detection is now 100% data-driven via `DepartmentDomainRepository`.
  - New model `DepartmentDomainMaster` (`backend/app/models/domain.py`): Id PK, DepartmentId FK → `OrgDepartmentMst.DeptID`, DomainName, Keywords (JSON text), DefaultRoles (JSON text), Priority, IsActive, CreatedOn, ModifiedOn.
  - New typed Pydantic schema `DepartmentDomain` (`backend/app/schemas/domain.py`).
  - New `backend/app/repositories/department_domain.py`: thread-safe in-memory cache (`threading.RLock`) with **precompiled keyword-regex matcher index** (`DomainMatcher`) built once and reused across every CV analysis. Load strategy: DB-first (join `OrgDepartmentMst` for dept names, ordered by Priority/Id), graceful fallback to bundled seed `backend/app/data/department_domains_seed.json` when the DB is unreachable/empty (mirrors `ConfigRepository` degradation). Exposes `get_all_domains()`, `get_domain_by_department()`, `get_domain_matchers()`, `refresh_cache()`; module singleton `department_domain_repository`, injectable via `ScoringEngine.domain_repository` class attribute.
  - `ScoringEngine.extract_candidate_domain_profile` + `_build_domain_candidate_text` now consume the repository; keyword-count tie-break uses `Priority` to preserve the legacy first-defined-wins ordering. No-domain fallback strings kept as `DEFAULT_*` class constants (generic defaults, not department data).
  - Wired `warm_department_domains()` into `cache_warmer.warm_all` (also covers startup thread + `/master-data/warm`). Returns 0 gracefully when `SessionLocal` is None.
  - Migration `backend/scripts/migrations/002_create_department_domain_master.sql`: idempotent CREATE TABLE + guarded FK + seed INSERTs resolving `DepartmentId` from `OrgDepartmentMst` by name.
  - New tests `backend/tests/test_department_domain_repository.py` (11 tests): seed fallback, legacy-value parity, `get_domain_by_department`, `refresh_cache` reload, precompiled matcher behavior, preserved `extract_candidate_domain_profile` results (IT/Finance/Plant + generic fallback), **new department via seed without any code change**, `_build_domain_candidate_text` inference, and thread-safety smoke test.
  - Validation: `pytest tests/test_department_domain_repository.py` (11 passed), `tests/test_domain_matching.py` + `tests/test_taxonomy_integration.py` (all passed except pre-existing `test_no_suitable_active_vacancy_summary`), `tests/test_audit_fixes.py` domain/department/match/scoring + cache-warmer subsets passed. Log confirms seed fallback (`[DEPARTMENT_DOMAIN] Loaded 8 active domain(s) from seed.`). New-code lint clean; only pre-existing project-wide `BLE001` broad-except pattern remains in the new repository (consistent with `ConfigRepository`/`cache_warmer`).

- **Automated Integration Tests for Resume Classification & Vacancy Pre-Filtering**:
  - Created `backend/tests/test_taxonomy_integration.py` (7 tests, all passing) covering the 4 requested Test Cases against CURRENT system behavior:
    - **TC1 Desktop Support Engineer**: Asserts `TaxonomyClassifier.classify_candidate` returns `DOMAIN_IT_SOFTWARE` with `FAMILY_IT_NETWORKING_AV` (the "Infrastructure / Desktop Support" family), domain profile maps to `recommended_department="Information Technology"` / `professional_domain="Information Technology & Software"`, and Production / QC / Mechanical / Electrical Plant (plus Finance & HR) vacancies are pruned in Stage-0 taxonomy pre-filter before scoring.
    - **TC2 Software Developer**: Asserts Finance / HR / Production / QC / Mechanical / Electrical Plant vacancies are excluded before retrieval. DOCUMENTED DIVERGENCE: IT Infrastructure vacancies (Desktop Support / Network Engineer) are NOT excluded today because `COMPATIBILITY_MAP` marks the Software and IT Infrastructure families as mutually compatible.
    - **TC3 Mechanical Engineer**: Asserts `classify_candidate` returns `DOMAIN_OTHER` / `[FAMILY_OTHER]`, so Stage-0 taxonomy pruning is a no-op today (DOCUMENTED DIVERGENCE from the "Software/Desktop/Network excluded" spec); profile maps to Plant & Maintenance with "Mechanical Engineer" in suitable roles; non-IT vacancies pruned for IT candidates survive the pre-filter for a Mechanical candidate.
    - **TC4 No matching vacancies**: Asserts current contract (`has_genuine_match=False`, `active_vacancy_summary`, processing `status="COMPLETED"`) instead of `{"status":"NO_SUITABLE_VACANCY"}` (DOCUMENTED DIVERGENCE); recommended department / professional domain / suitable job roles still returned; no unrelated vacancy recommended (all classification `LOW`, score < `MATCH_MEDIUM_THRESHOLD`).
  - Tests are hermetic & fast (~7s): autouse fixture clears caches, disables embeddings (`EMBEDDING_ENABLED=False`), and stubs `OllamaLLMService.run_optimized_match` so the pipeline exercises taxonomy classification → Stage-0 pre-filter → deterministic scoring end-to-end without Ollama/DB/Redis.
  - Verified via `.venv/bin/pytest tests/test_taxonomy_integration.py` (7 passed) and `ruff check`/`ruff format` clean.
  - NOTE: `tests/test_domain_matching.py::test_no_suitable_active_vacancy_summary` is currently failing (asserts `active_vacancy_summary == "No suitable active vacancy found."` while the service returns the longer "…matching candidate domain/taxonomy profile…" string; also hangs ~30s per LLM attempt). Not modified as part of this task.

- **Abdul Mannan CV Live Pipeline Audit & Domain Mismatch Evaluation**:
  - Processed `Resume Abdul Mannan 1.pdf` through the live pipeline against the real 107-vacancy dataset (Aarti Industries live DB) and default pre-filter.
  - Extracted profile: B.E. Electronics & Telecommunication Engineering with 4+ years in AV & IT Networking Systems (Dante, Crestron, Q-Sys, Cisco switches, routers, VLANs).
  - Evaluated Top-5 shortlisted vacancies from pre-filter RRF output (`[1208] Executive (MEE)`, `[995] Engineer (Process and Project)`, `[1064] Engineer (Process and Project)`, `[1066] Software Developer`, `[1126] Technical Leader (R&D)`) with 8-component breakdowns.
  - Confirmed domain mismatch guard behavior & identified domain guard gap: AV/Networking candidates scoring against Industrial Electrical/C&I/Utility roles are not covered as a mismatch pair, leading to inflated scores (78.5% on Plant Electrical, 71.0% on C&I Lead) due to "Electronics & Telecommunication" degree and hardware token overlap.

- **Background Task Cleanup**: Checked and terminated all background tasks (`task-162` pytest task). Zero active background tasks or subagents remain running.
- **Full Backend Diagnostic Audit**: Completed (66 files audited, 14 findings identified).
- **Full Frontend Diagnostic Audit & Gap Analysis**: Completed across 7 routes, 17 UI components, 6 hooks, and 10 API services.
- **Candidate Recommendations Feature Audit & Overhaul**: Completed.
- **Pipeline 71% Hang & Status Synchronization Desync Root Cause & Fix**:
  - `backend/app/api/analysis.py`: Updated `/api/match/status/{cv_key}` to check whether `result` is completed (`status in ("COMPLETED", "NEW_CV", "REPROCESSED")` or `progress == 100` or `is_complete is True`). If `match_analysis` sub-dict is omitted or missing, it returns a `CVProcessingResponse` with `status="COMPLETED"`, `progress=100`, `stage="complete"`.
  - `frontend/src/hooks/useCvUpload.ts`: Updated `pollCvStatus` (`isEnriched = true`) completion condition to check `scan_id`, `match_analysis`, `status === 'COMPLETED'`, `status === 'NEW_CV'`, `status === 'REPROCESSED'`, `progress === 100`, or `is_complete === true`.
  - `backend/app/repositories/result.py`: Refined `ResultRepository.resolve_result(cv_key)` to check alternative key/stem/scan_id candidates for a completed result (`status != "processing"`) before settling on a direct-match interim `processing` result.
- **Candidate Search 500 Error Fix**:
  - `backend/app/services/candidate_search_service.py`: Added missing `RuleConfigManager` import (`from app.core.rule_config_manager import RuleConfigManager`), resolving `NameError` on `POST /api/v1/candidates/search` and returning candidate search items with rule-config confidence tiers.
  - Updated `run.md` with Redis service startup commands (`brew services start redis` / `brew services restart redis` / `redis-server`), connection test command (`redis-cli ping`), `.env` `REDIS_URL=redis://localhost:6379/0` configuration, and port 8000 cleanup command (`kill -9 $(lsof -t -i:8000)`).
- **Audit & Confirmation of Selective Invalidation Rules in `cache.py`**: Completed.
  - Replaced naive string pattern checks in [`MemoryCache._match_pattern`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/core/cache.py#L187-L192) with standard library `fnmatch.fnmatch` for accurate glob matching on namespaced keys (e.g. `cv_result:*cand_1*`).
  - Configured `doc_cache_manager`, `cv_result_cache_manager`, and `llm_cache_manager` to include `_memory_cache` (L1 Memory), `_redis_cache` (L2 Redis), and `FileCache` (L3 Disk) so cache deletion operations run through all tiers simultaneously.
  - Normalized candidate ID handling in `CacheInvalidator.invalidate_candidate` (`cand_` prefix stripping) and added `cv_result_cache_manager` purging to `invalidate_cv`.
  - Added dual Redis/In-Memory secondary index fallback (`_in_memory_index`) to [`CacheIndex`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/core/cache.py#L533-L582) so dependency tracking works seamlessly in both standalone and Redis environments.
  - Eliminated overbroad full-cache purge in [`CacheInvalidator._invalidate_match_results_by_doc`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/core/cache.py#L628-L633) that previously wiped all match results across all candidates during single document invalidation.
- **Canonical Key Standardization & Lifecycle 0->100 Verification**:
  - Standardized `get_stable_cv_key` in [`backend/app/services/cv_service.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/cv_service.py#L33-L44) to return a single canonical `cv_{safe_stem}` across all upload paths (`/cv/upload` and `/match/upload`) and processing lifecycle stages (interim status, final save, status polling).
  - Empirically verified via [`verify_fresh_cv_lifecycle.py`](file:///Users/khushaldhanani/.gemini/antigravity-cli/brain/2f2ebb07-7904-4964-9a4c-b0921ea1079e/scratch/verify_fresh_cv_lifecycle.py) that a fresh CV upload progresses continuously (15% -> 30% -> 45% -> 60% -> 75% -> 90% -> 100%) under one consistent key with 0% polling desync.
- **Multi-Tier Cache Simplification**:
  - Implemented dynamic `active_providers` in [`CacheManager`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/core/cache.py#L440-L455): when Redis is active (`_REDIS_CLIENT is not None`), `FileCache` (L3) is bypassed during reads and writes to eliminate FileLock disk contention, while retaining `FileCache` as persistent fallback when Redis is down.

- **Background Task Cleanup**:
  - Checked and terminated all background processes (`task-472` pytest process). Zero active background tasks or subagents remain running.
- **Real Data Job Title & Company Name Verification**:
  - Confirmed `is_valid_job_title("ASP .NET Developer")` evaluates to `True`.
  - Verified 0 regressions across all historical CV titles/companies in the project (Utkarsh Patil, Tarun Gupta, Jane Smith, Alex Johnson, John Doe, synthetic/polling load test CVs).
- **Gazetteer Extension & Regional Location Confidence Tier Upgrade**:
  - Extended `KNOWN_GAZETTEER` in [`backend/app/services/document_parser.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/document_parser.py#L344-L354) with regional locations: Surat, Vadodara, Rajkot, Gujarat, Gandhinagar, Bhavnagar, Jamnagar, Junagadh, Anand, Vapi, Ankleshwar, Navsari, Bharuch, Mehsana, Morbi, Maharashtra, Karnataka, Tamil Nadu, Telangana, Haryana, Uttar Pradesh, Kerala, Punjab, Rajasthan.
  - Empirically verified via [`scratch/verify_verifications.py`](file:///Users/khushaldhanani/.gemini/antigravity-cli/brain/c410d448-84ba-451e-a7b7-b6e4bcdee574/scratch/verify_verifications.py) that candidate locations now elevate to `0.90` (`HIGH` confidence tier) instead of `0.50` (`MEDIUM`).
- **Unified RuleConfigManager Implementation & Consolidation**:
  - Implemented [`backend/app/core/rule_config.json`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/core/rule_config.json) consolidating keyword lists, gazetteers, confidence scoring weights, tier thresholds (`high_min`, `medium_min`, `low_min`), and downstream acceptance gates into a single version-controlled configuration.
  - Implemented [`backend/app/core/rule_config_manager.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/core/rule_config_manager.py) with Pydantic model validation enforcing three critical safety invariants:
    1. `override_reason` mandatory requirement when a field's threshold deviates from global tiers.
    2. `min_acceptance_confidence` strictly greater than `email_username_fallback` score (0.30).
    3. `min_acceptance_confidence` $\ge$ `medium_min` for the same field (preventing gate/threshold decoupling).
  - Integrated a 4-case in-memory synthetic smoke test suite running prior to atomic config activation (testing location blacklist, job title narrative rejection, company header rejection, and gate/medium_min decoupling rejection).
  - Refactored [`ResumeJsonExtractor`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/document_parser.py) to delegate keywords and thresholds dynamically to `RuleConfigManager`.
  - Empirically verified via [`backend/tests/test_rule_config_manager.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/tests/test_rule_config_manager.py) (100% test pass across 16 test cases).

- **Per-Field Confidence UI Extension Across All 4 Rule-Config Fields**:
  - **Audit & Confirmation**: Confirmed that candidate list (`frontend/src/app/candidates/index.tsx`) and detail (`frontend/src/app/candidates/[id].tsx`) screens previously only rendered name fallback treatment ("Name not detected") and completely lacked per-field confidence tier badges or treatment for `location`, `job_title`, and `company_name`.
  - **Backend API Tier Resolution & Gap Fix**: Confirmed that backend API responses previously only returned raw float scores for `name_confidence` (or nested `field_confidence`), forcing frontend to bucket thresholds manually. Added `get_confidence_tier(field_name, score)` to [`backend/app/core/rule_config_manager.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/core/rule_config_manager.py#L157-L176) to resolve `"HIGH"`, `"MEDIUM"`, or `"LOW"` directly based on `rule_config.json` thresholds.
  - **API Schemas & Responses Extended**: Updated [`CVUploadResponse`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/schemas/cv.py#L67-L77), [`CandidateSearchResultItem`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/schemas/candidate_search.py#L27-L38), [`cv_service.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/cv_service.py#L237-L290), and [`candidate_search_service.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/candidate_search_service.py#L208-L232) to return top-level `location`, `job_title`, `company_name`, `name_confidence_tier`, `location_confidence_tier`, `job_title_confidence_tier`, `company_name_confidence_tier`, and `field_confidence_tiers` dictionary.
  - **Reusable Frontend Confidence View**: Built [`FieldConfidenceView.tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/FieldConfidenceView.tsx#L1-L50) in `frontend/src/components/ui` enforcing the required behavior:
    1. Null/empty value $\rightarrow$ `"[Field] not detected"` in muted text (`text-text-faint italic`).
    2. `LOW`/`MEDIUM` confidence tier $\rightarrow$ small `"Unverified"` warning badge next to the value.
    3. `HIGH` confidence tier $\rightarrow$ standard crisp text without warning badge.
  - **Candidate List & Detail UI Extension**: Integrated `FieldConfidenceView` into candidate list rows ([`frontend/src/app/candidates/index.tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/index.tsx#L40-L95)) and candidate profile metadata banner ([`frontend/src/app/candidates/[id].tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/[id].tsx#L288-L345)).
  - **Empirical Verification**: Verified backend test suite ([`backend/tests/test_rule_config_manager.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/tests/test_rule_config_manager.py#L76-L88)) with 100% test pass.

- **Mandatory Failure Surfacing & Education Failure Visibility**:
  - **Audit & Confirmation**: Checked candidate detail screen ([`frontend/src/app/candidates/[id].tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/[id].tsx#L690-L745)) and [`MatchAnalysisCard.tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/MatchAnalysisCard.tsx#L95-L140). Found that Top Job Match card previously omitted mandatory failure blocks entirely, while `MatchAnalysisCard` only checked `bestMatch.mandatory_fails` and silently dropped `mandatory_failures` / `missing_criteria` if formatted as objects. Additionally, the missing qualifications section header was mislabeled strictly as `"Identified Skill Gaps:"`.
  - **Backend Dual-Field Normalization**: Updated [`JobMatchScore`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/schemas/match.py#L109-L114) and [`scoring_engine.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/scoring_engine.py#L1064-L1072) to populate both `mandatory_failures` (detailed objects) and `mandatory_fails` (summary list with `requirement`, `details`, `severity`) so education domain mismatch failures and skill/experience failures are uniformly available in all API JSON representations.
  - **Match Analysis Card Enhancement**: Refactored [`MatchAnalysisCard.tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/MatchAnalysisCard.tsx#L95-L140) to normalize `mandatory_fails`, `mandatory_failures`, `mandatory_requirements`, and `missing_criteria`. Education failures (e.g. `Education: Mandatory education 'BTech Computer Science' not found in CV`), domain mismatch failures (`req_domain_mismatch`), and skill/experience failures are now rendered explicitly in a styled warning card.
  - **Top Job Match & AI Recommendations Surfacing**: Added the mandatory requirement failures & missing criteria section directly inside the Top Job Match card on [`frontend/src/app/candidates/[id].tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/[id].tsx#L705-L755), and relabeled the recommendations gap section to `"Identified Mandatory Gaps & Missing Qualifications:"` so education failures are surfaced accurately alongside skill gaps.
- **Domain Mismatch Guard Explainability & Score-Capped Surfacing**:
  - **Audit & Confirmation**: Confirmed an explainability gap where cross-domain score capping (e.g. software candidate evaluated against plant/chemist role, capping score at $\le 20\%$) dropped the match score without informing recruiters why the score was penalized.
  - **Backend Score Breakdown Extension**: Extended [`JobMatchScore`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/schemas/match.py#L127-L135) with `domain_mismatch_capped: bool` and `domain_mismatch_reason: str`. Updated [`scoring_engine.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/scoring_engine.py#L1030-L1082) and [`candidate_search_service.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/candidate_search_service.py#L220-L235) to populate these fields whenever cross-domain guard triggers or `req_domain_mismatch` is present.
  - **Frontend UI Flag & Explainability Callouts**:
    1. **Candidate List Screen** ([`frontend/src/app/candidates/index.tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/index.tsx#L105-L125)): Rendered `<Badge label="Cross-domain match — score capped" tone="warning" />` in candidate row trailing score section.
    2. **Candidate Detail Screen** ([`frontend/src/app/candidates/[id].tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/[id].tsx#L680-L715)): Added `"Cross-domain match — score capped"` warning badge to Top Job Match header and rendered a prominent yellow callout banner explaining the exact domain conflict.
    3. **`MatchAnalysisCard` Component** ([`frontend/src/components/ui/MatchAnalysisCard.tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/MatchAnalysisCard.tsx#L30-L85)): Added badge and explainability banner whenever domain mismatch capping is active.
- **Progress / Polling E2E Regression Verification**:
  - **Frontend UI Polling Audit**: Verified the complete polling lifecycle in [`useCvUpload.ts`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/hooks/useCvUpload.ts#L89-L304) and [`StepProgressCard.tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/StepProgressCard.tsx#L100-L176). Confirmed that frontend polling checks `scan_id`, `match_analysis`, `status === 'COMPLETED'`, `status === 'NEW_CV'`, `status === 'REPROCESSED'`, `progress === 100`, or `is_complete === true` to trigger smooth 0 $\rightarrow$ 100% completion.
  - **End-to-End Simulation & Verification**: Built and executed [`scratch/verify_frontend_polling_e2e.py`](file:///Users/khushaldhanani/.gemini/antigravity-cli/brain/b0e712d5-2ebb-4bd2-8308-20718a14ade0/scratch/verify_frontend_polling_e2e.py) simulating a real document upload against `/api/match/upload` and `/api/cv/upload`. Observed continuous progress progression: 15% (validation/parsing) $\rightarrow$ 35% (extraction) $\rightarrow$ 50% (ai_analysis) $\rightarrow$ 75% (matching) $\rightarrow$ 100% (complete), confirming 0% polling desync, 0% stall at 71%, and smooth pipeline rendering.
- **`retrieval_source` Exposure & Subtle UI Surfacing**:
  - **Backend Audit & Field Exposure**: Identified that while [`VacancyPreFilter`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/vacancy_prefilter.py#L180-L215) performs RRF fusion (computing `lexical_rank` and `vector_rank`), the resulting `retrieval_source` (`"both"`, `"vector"`, `"keyword"`) was previously dropped by `scoring_engine.py` and absent from [`JobMatchScore`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/schemas/match.py#L130-L138).
  - **Backend Implementation**: Added `retrieval_source: str | None` to [`JobMatchScore`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/schemas/match.py#L135-L138), updated [`scoring_engine.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/scoring_engine.py#L1040-L1090) to derive `retrieval_source` from `_rrf_details` (`both`, `vector`, `keyword`), and updated [`candidate_search_service.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/candidate_search_service.py#L250-L262) to pass `retrieval_source` in search responses.
  - **Subtle Frontend UI Surfacing**: Confirmed and verified that [`MatchAnalysisCard.tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/MatchAnalysisCard.tsx#L18-L58) and [`[id].tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/[id].tsx#L664-L682) render subtle badge tags:
    - `"both"` $\rightarrow$ `<Badge label="Hybrid (Keyword + Vector)" tone="success" />`
    - `"vector"` $\rightarrow$ `<Badge label="pgvector Match" tone="info" />`
    - `"keyword"` $\rightarrow$ `<Badge label="Keyword Match" tone="neutral" />`
- **`.docx` Structural Validation Error Messaging**:
  - **Backend Structural Validation**: Updated [`MarkdownGenerator`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/document_parser.py#L873-L886) to perform explicit ZIP archive validation (`zipfile.is_zipfile`) and `word/document.xml` existence checks on uploaded `.docx` files.
  - **Specific Error Surfacing**: When a fake or corrupted `.docx` file is uploaded (e.g. plain text file or corrupted archive with `.docx` extension), backend raises `ValueError("Invalid Word document: The uploaded file is not a valid .docx document structure (corrupted file or invalid archive).")`.
  - **Frontend UI Error Rendering**: Confirmed that [`useCvUpload.ts`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/hooks/useCvUpload.ts#L115-L125) catches the failed status message and passes it directly to [`StepProgressCard.tsx`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/StepProgressCard.tsx#L189-L213), displaying `"Invalid Word document: The uploaded file is not a valid .docx document structure"` in red error callout UI rather than a generic parse error.
  - **Empirical Verification**: Created [`backend/tests/test_docx_validation.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/tests/test_docx_validation.py) and verified test pass via `pytest` (100% pass across structural error cases).

- **`types/api.ts` Strict Field Classification & Type Safety Enforcement**:
  - **Bucket Classification & Audit**: Audited all fields in [`frontend/src/types/api.ts`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/types/api.ts) against Pydantic models in [`backend/app/schemas/match.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/schemas/match.py) and [`backend/app/schemas/analysis.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/schemas/analysis.py).
  - **Bucket 2 Enforcement (Always Present / Non-Optional)**:
    - Standardized all 8 component scores on `JobMatchScore` (`role_score`, `skills_score`, `experience_score`, `education_score`, `domain_score`, `technology_score`, `certification_score`, `responsibilities_score`) as **required `number`** (never optional).
    - Standardized `coverage`, `confidence`, `hr_review_required`, `career_transition_detected`, `domain_mismatch_capped`, `matched_skills`, `missing_skills`, `matched_criteria`, `missing_criteria`, `evidence`, and `rejection_policy_note` as **required** fields.
  - **Bucket 1 Enforcement (Genuinely Conditional)**:
    - Retained `career_transition_note` (`string | null`) and `domain_mismatch_reason` (`string | null`) as optional/nullable since they are present only when a transition or domain mismatch occurs.
    - Verified `HRReviewRequest` contract: `feedback_notes: string` is **required** (HR review notes must always be supplied), while `corrected_score` and `corrected_classification` are **optional/nullable** (enabling HR notes-only approval without score override).

- **Dual Upload Endpoint Key & Storage Alignment Verification**:
  - **Empirical Execution & Comparison**: Executed dual upload simulation ([`scratch/verify_dual_upload_key_alignment.py`](file:///Users/khushaldhanani/.gemini/antigravity-cli/brain/b0e712d5-2ebb-4bd2-8308-20718a14ade0/scratch/verify_dual_upload_key_alignment.py)) uploading an identical file (`dual_upload_test_resume.txt`) through `/api/cv/upload` (fast-track) and `/api/match/upload` (enriched).
  - **Empirical Proof**:
    - `cv_key` returned by `/api/cv/upload`: `'cv_dual_upload_test_resume'`
    - `cv_key` returned by `/api/match/upload`: `'cv_dual_upload_test_resume'`
    - Keys match exactly: `True`
    - Result files in `RESULTS_DIR`: `['cv_dual_upload_test_resume.json']` (exactly 1 file)
    - Both `ResultRepository.resolve_result` and `ResultRepository.read_result_by_filename` resolve to the exact same single entry (`scan_id='cv_dual_upload_test_resume'`).
  - **Automated Test Suite**: Created [`backend/tests/test_dual_upload_key_alignment.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/tests/test_dual_upload_key_alignment.py) asserting 0 key divergence, single result file persistence, and uniform repository resolution (100% test pass).

## Files Modified
- `backend/app/models/domain.py`
- `backend/app/schemas/domain.py`
- `backend/app/repositories/department_domain.py`
- `backend/app/data/department_domains_seed.json`
- `backend/scripts/migrations/002_create_department_domain_master.sql`
- `backend/app/services/cache_warmer.py`
- `backend/app/services/scoring_engine.py`
- `backend/tests/test_department_domain_repository.py`
- `backend/tests/test_taxonomy_integration.py`
- `backend/tests/test_domain_matching.py`
- `workstatus.md`
- `backend/app/core/cache.py`
- `backend/app/core/rule_config.json`
- `backend/app/core/rule_config_manager.py`
- `backend/app/schemas/cv.py`
- `backend/app/schemas/match.py`
- `backend/app/schemas/candidate_search.py`
- `backend/app/services/candidate_search_service.py`
- `backend/app/services/cv_service.py`
- `backend/app/services/document_parser.py`
- `backend/app/services/vacancy_prefilter.py`
- `backend/tests/test_rule_config_manager.py`
- `backend/tests/test_frontend_polling_e2e.py`
- `backend/tests/test_docx_validation.py`
- `backend/tests/test_dual_upload_key_alignment.py`
- `backend/app/services/llm_service.py`
- `backend/app/prompts/profile_extraction.py`
- `backend/app/prompts/optimized_match.py`
- `backend/app/prompts/match_analysis.py`
- `backend/app/prompts/dynamic_mapping.py`
- `backend/tests/test_qwen_llm_service.py`
- `workstatus.md`


- **Data-Driven Role Matching Replacement**:
  - **Removed Hardcoded Logic**: Completely removed the hardcoded keyword-to-role list `_ROLE_INFERENCE_PATTERNS` in [`candidate_domain_service.py`](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/candidate_domain_service.py).
  - **Dynamic Engine Implementation**: Rewrote `_infer_roles_from_resume` to dynamically classify roles using the JSON-configured `TaxonomyClassifier` and intersection with dynamically loaded `DepartmentDomainRepository` matching rules.
  - **Dynamic Strengths Extraction**: Refactored `_extract_strengths_from_resume` to dynamically obtain the fallback domain from `RuleConfigManager` and construct strengths dynamically rather than via literal string fallbacks.
