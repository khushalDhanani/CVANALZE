# Work Status

## Work Completed — Phase 1: Fail-safe Production Configuration
- **Disabled static JSON and hardcoded prompt fallbacks in production**: Updated `rule_config_manager.py` and `optimized_match.py` to check `settings.IS_PRODUCTION` before falling back to static files or strings.
- **Removed route-level localhost fallbacks**: Removed hardcoded `redis://localhost:6379/0` fallbacks in `cv_service.py`, `batch.py`, and `tasks.py`.
- **Introduced last-known-good configuration caching**: Implemented logic in `rule_config_manager.py` and `optimized_match.py` to persist successful DB loads into `config_cache_manager` and use them as a fallback if the DB becomes unavailable.
- **Added explicit failures**: Added `SystemConfigurationError` and `PromptError` to `error_handlers.py` alongside `CONFIGURATION_UNAVAILABLE` and `PROMPT_UNAVAILABLE` error codes in `contracts.py` mapped to HTTP 503.
## Work Completed — CV Work Experience Extraction Engine
- **Implemented decoupled extraction architecture**: Created `WorkExperienceExtractionEngine` to orchestrate LLM evidence extraction separately from deterministic date calculation, policy filtering, and deduplication.
- **Added Ollama standardized LLM schema integration**: Extended `OllamaLLMService` with `extract_work_experience()` method which wraps `_execute_structured_generation`, using strict Pydantic JSON schema matching (`LLMWorkExperienceExtraction`).
- **Implemented dynamic date/overlap calculation engine**: Added `WorkExperienceCalculationService` that merges overlapping and adjacent work experience intervals properly according to config, tracks gross vs unique days, handles leap years/month-end boundaries natively via `dateutil`.
- **Implemented deduplication and policy filtering logic**: Added `WorkExperiencePostProcessor` that deterministically filters records based on employment type (e.g. dropping internships if requested) and deduplicates OCR records based on a weighted fuzzy match on Job Title, Company, and dates.
- **Exposed REST API endpoint**: Added `POST /api/v1/cv/extract-experience` supporting comprehensive requests (reference_date, config policies) returning human-review warnings and complete unique experience summaries.
- **Test suite (100% pass)**: Implemented extensive pytest cases (`tests/services/test_work_experience_post_processor.py`, `tests/services/test_work_experience_calculation_service.py`, `tests/services/test_work_experience_extraction_service.py`, `tests/api/test_experience_extraction_api.py`) covering leap years, ordinals, human review logic, overlap math, missing dates, etc.

## Work Completed
- Diagnosed the root cause of the UI only displaying 5 vacancies. The application was failing to connect to the MSSQL database and was returning a fallback mock list.
- Identified that the failure was due to missing `pyodbc` Microsoft drivers (`msodbcsql18`) in the Docker image and missing `DB_*` environment variables in `docker-compose.yml`.
- Updated `docker-compose.yml` to pass down MSSQL database credentials (`DB_SERVER`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`).
- Updated `docker-compose.local.yml` to set `INSTALL_MSSQL_ODBC: "true"` for both `api` and `worker` services.
- Successfully rebuilt and restarted the `api` and `worker` docker containers. The build downloaded and installed the necessary Debian MS ODBC packages.
- **Fixed "SUITABLE JOB MATCH" mislabeling bug**:
  - Backend: Split `evaluated_matches` into `suitable_openings` (HIGH/MEDIUM) and `unsuitable_openings` (LOW) in both `MatchService` and `ScoringEngine`.
  - Backend: Added `unsuitable_openings` field to both `EnrichedCandidateAnalysis` and `CandidateMatchAnalysis` schemas.
  - Frontend: Replaced hardcoded index-based label with classification-aware labels (HIGH → "Top Job Match"/"Strong Match", MEDIUM → "Potential Match").
  - Frontend: Added "Manual Review Required" section for LOW-classified vacancies with warning styling.
- **Fixed "Experience & Seniority: N/A" & Calculation Bugs (Generic Cross-Platform Pipeline)**:
  - Created reusable `DateIntervalParser` module (`date_interval_parser.py`) supporting locale-aware date parsing (English, Spanish, French, German), ISO dates, seasons/quarters, fuzzy strings, 2-digit years, parenthetical ranges, and present synonyms (`present`, `current`, `till date`, `onwards`, `heute`, `aujourd'hui`).
  - Integrated `DateIntervalParser` into `ResumeNormalizer` (`resume_normalizer.py`) to output typed `NormalizedDateInterval` objects with confidence levels and evidence lists.
  - Fixed premature `commit()` logic in `ResumeFieldExtractor._extract_employment()` (`resume_field_extractor.py`) so multi-line job headers are joined with dates instead of being split.
  - Implemented `ExperienceCalculator.calculate_canonical_experience()` (`experience_calculator.py`):
    1. Preserves raw employment text and raw date strings.
    2. Logs unparsed dates with candidate ID, role index, and raw string (`[EXPERIENCE_DATE_PARSE_UNSUPPORTED]`).
    3. Handles ongoing/present roles by defaulting to current date.
    4. Merges overlapping employment intervals without double-counting.
    5. Counts same-month roles as at least 1 active month.
    6. Ensures deterministic date-derived experience is authoritative and cannot be overridden by LLM or stated experience.
    7. Derives canonical seniority levels (`Executive / Director`, `Lead / Principal`, `Senior`, `Mid-Level`, `Junior / Associate`, `Entry Level`).
    8. Documented employment roles never default to `0.0`, `Junior`, or `N/A` (falls back to stated experience or role-count heuristic if dates are unparseable).
  - Exposed top-level `experience_years`, `seniority`, `experience_summary`, and `work_experience` across `cv_service.py`, `candidates.py` (`GET /api/v1/candidates/{id}`), and `recommendation_service.py`.
  - Updated frontend `[id].tsx` to render Experience & Seniority badge in the candidate header bar, Experience Timeline with fallback keys, and Hiring Intelligence assessment text directly.
  - Added new regression test suites `test_date_interval_parser.py`, `test_experience_date_formats.py`, and `test_experience_canonical.py` (15/15 unit tests passing 100%).
- **Fixed Candidate Directory Missing Scanned CVs Bug (Redis + Disk Result Merging)**:
  - Discovered that candidate result records stored in Redis (`cv_gptsuifgr321345678o9p.json` and `cv_ut1765894215.json`) were being ignored because `ResultRepository.list_all_results()` previously only scanned disk files in `uploads/results/`.
  - Updated `ResultRepository.list_all_results()` (`result.py`) to merge Redis cache entries (`cv_result:*.json`) with disk files, deduplicating by candidate/scan ID.
  - Added `./backend/uploads:/app/uploads` volume mount to both `api` and `worker` in `docker-compose.local.yml`.
  - Rebuilt containers (`docker compose up -d --build api worker`). Candidate search now returns all 5 candidates (`cv_Utkarsh_Patil_07012026sdfgdfvdfsf`, `cv_gptsuifgr321345678o9p`, `cv_ut1765894215`, `candidate-1`, `candidate-2`).
- **Updated `run.md`**:
  - Added Docker Compose full-stack startup commands.
  - Added Docker container rebuild command (`up -d --build api worker`) for updating backend changes.
  - Added log monitoring and container management commands.

## Files Changed
- `docker-compose.yml`
- `docker-compose.local.yml` — added `./backend/uploads:/app/uploads` volume mounts for `api` and `worker`
- `run.md` — updated with Docker Compose commands, container rebuild steps, and log monitoring
- `backend/app/repositories/result.py` — updated `ResultRepository.list_all_results()` to scan both Redis cache and disk files
- `backend/app/schemas/analysis.py` — added `unsuitable_openings` field to `EnrichedCandidateAnalysis`
- `backend/app/schemas/match.py` — added `unsuitable_openings` field to `CandidateMatchAnalysis`
- `backend/app/services/date_interval_parser.py` — new generic locale-aware date interval parsing module
- `backend/app/services/candidate_search_service.py` — normalized status filter matching in candidate search
- `backend/app/services/match_service.py` — split evaluated matches by classification threshold
- `backend/app/services/scoring_engine.py` — split evaluated matches by classification threshold
- `backend/app/services/resume_field_extractor.py` — expanded `_DATE_RANGE` regex and fixed `_extract_employment` entry commit logic
- `backend/app/services/experience_calculator.py` — integrated `DateIntervalParser`, canonical calculation, unparsed date logging, and interval merging
- `backend/app/services/resume_normalizer.py` — integrated `DateIntervalParser` for typed `NormalizedDateInterval`
- `backend/app/services/cv_service.py` — attached top-level `experience_years`, `seniority`, `experience_summary`, and `work_experience`
- `backend/app/api/candidates.py` — dynamically attached canonical experience on candidate detail endpoint for legacy records
- `backend/app/services/recommendation_service.py` — multi-tier fallback using canonical experience calculator
- `frontend/src/app/candidates/[id].tsx` — added Experience & Seniority header badge + classification-aware labels + Experience Timeline schema alignment
- `backend/tests/test_date_interval_parser.py` — new test suite for locale-aware date parsing
- `backend/tests/test_experience_date_formats.py` — new test suite for date extraction formats
- `backend/tests/test_experience_canonical.py` — new test suite for canonical experience calculation

## Pending Work
- None currently.

## Important Decisions
- **Redis + Disk Result Merging**: `ResultRepository.list_all_results()` now scans Redis keys `cv_result:*.json` in addition to disk files, so candidates saved in Redis cache immediately show up in the candidate list UI even if saved prior to volume mounting.
- **Taxonomy Source of Truth**: `TaxonomyService` is now the single source of truth for the `compatibility_map`, completely deprecating the static JSON file and decoupling `RuleConfigManager` from taxonomy rules.

---

## Work Completed — Phase 3: Database-Driven Taxonomy and Rules (Backend Audit Report)

### Bug Fixes & Refactoring
- **`app/services/taxonomy_service.py`**: Updated to load `FamilyCompatibility` from the database and cache it in memory, exposing `get_compatibility_map()`.
- **`app/services/job_taxonomy.py`**: Switched from using static JSON rules to dynamically fetching `COMPATIBILITY_MAP` via `TaxonomyService`.
- **`app/core/rule_config_manager.py`**: Removed `compatibility_map` field from the `TaxonomyRules` Pydantic model and deleted associated validation gates in `validate_taxonomy_config`.
- **`scripts/seed_taxonomy_from_json.py`**: Updated script to handle the removal of the compatibility map from the runtime schema by directly reading the JSON during DB seeding.

### Test Fixes
- **`tests/test_audit_fixes.py`**: 
  - Fixed `test_docx_upload_full_pipeline` and `test_cv_upload_background_task_returns_processing_status` by properly mocking `QueueSubmission` in `ProcessingQueueService` instead of the legacy `background_process_cv`.
  - Fixed `test_vacancy_cache_compute_hash` by aligning the ID-hashing logic with `compute_matching_vacancy_version` so data changes invalidate the cache properly.
- **`tests/test_taxonomy_integration.py`**: Rewired tests to mock the database instead of the JSON config via `TaxonomyService`.

## Files Changed
- `backend/app/services/taxonomy_service.py`
- `backend/app/services/job_taxonomy.py`
- `backend/app/core/rule_config_manager.py`
- `backend/app/repositories/job.py`
- `backend/scripts/seed_taxonomy_from_json.py`
- `backend/tests/test_rule_config_manager.py`
- `backend/tests/test_taxonomy_integration.py`
- `backend/tests/test_audit_fixes.py`

---

## Work Completed — Designation Classification Overhaul (2026-08-05)

### Bug Fixes (Runtime-Breaking `AttributeError` crashes)
- **`dynamic_taxonomy_service.py`**: Removed duplicate `DepartmentNormalizer` import; fixed `_try_vector_semantic_match` to use correct `NormalizedClassification` field names (`db_department_id`, `db_department_name`, `db_designation_id`, `db_designation_name`, `industry_department`, `industry_designation`, `industry_domain`) instead of old model fields (`family_id`, `family_name`, `designation_name`, `domain_name`). Lowered `_get_default_fallback` confidence from `0.5` → `0.0`.
- **`job_taxonomy.py`**: Fixed `classify_vacancy_dto()` and `classify_candidate_dto()` — both accessed `dyn_res.domain_name`, `dyn_res.family_name`, `dyn_res.matched_term` which do not exist on `NormalizedClassification`. Replaced with `dyn_res.industry_domain`, `dyn_res.db_department_name`, `dyn_res.evidence[0].matched_term`.
- **`dynamic_taxonomy_service.py`**: Fixed both `normalize_designation()` call sites — changed wrong key `["industry_department"]` to `["industry_designation"]`.

### Component 1 — Normalization Layer
- **`department_normalizer.py`**: `normalize_designation()` now has real logic — checks alias cache, strips parenthetical suffixes, expands `Sr.`/`Jr.`/`Mgr.` abbreviations, and returns `{"industry_designation": ...}` with the correct key.

### Component 2 — Remove Hardcoded Rules
- **`department_domains_seed.json`**: Added `industry_label` field to all 8 active entries. Removed broad cross-domain keywords (`sql`, `api`, `code`, `coding`, `web`, `database`) from CIS Team that caused non-IT candidates to be mis-classified as IT.
- **`candidate_domain_service.py`**: Fixed `dyn_res.domain_name`/`dyn_res.family_name` field access to use correct `NormalizedClassification` fields.

### Component 3 — LLM Response Validation
- **`candidate_context.py`**: Both `create()` and `apply_optimized_profile()` now validate LLM `professional_domains[0]` against DB canonical domains before applying. If invalid → logs warning and preserves deterministic classification.
- **`optimized_match.py`**: Prompt now injects valid DB department names from seed, requires `NO_SUITABLE_MATCH` when no domain fits, and requires per-field CV evidence citation.

### Component 4 — Cross-Domain Guard
- **`candidate_context.py`**: `is_software_cand` detection now uses `DynamicTaxonomyService.check_family_compatibility()` instead of hardcoded `software_candidate_patterns` keyword list.

### Component 5 — Evidence-Based Match Outputs
- **`analysis.py`**: Added `classification: NormalizedClassification | None` and `ai_career_suggestions: list[AISuggestion]` to `EnrichedCandidateAnalysis`. Backward compatible — both optional/default-empty.
- **`match_service.py`**: Imports `DynamicTaxonomyService`, builds `NormalizedClassification` per-candidate, populates `classification` and `ai_career_suggestions` on `EnrichedCandidateAnalysis`. When no genuine match, builds `AISuggestion` per suitable role.
- **`recommendation_service.py`**: Uses `classification.industry_department` for display labels when available; falls back to raw department string.

### Component 6 — Vacancy Service Normalization
- **`job.py`**: Added `industry_title: str | None` and `industry_department: str | None` to `JobOpening`.
- **`vacancy_service.py`**: Calls `DepartmentNormalizer.normalize_department()` and `normalize_designation()` to populate `industry_department` and `industry_title` on every `JobOpening`.
- **`job_preprocessor.py`**: Calls `DepartmentNormalizer` to populate `_precomputed_industry_dept` and `_precomputed_industry_title` on preprocessed job dicts.

### Tests Created
- `backend/tests/test_classification_normalization.py` — NormalizedClassification schema, DepartmentNormalizer, seed integrity
- `backend/tests/test_dynamic_taxonomy_evidence.py` — DynamicTaxonomyService fallback, evidence fields, no AttributeError
- `backend/tests/test_cross_domain_guard_db_driven.py` — DB-driven guard, no hardcoded patterns
- `backend/tests/test_llm_domain_validation.py` — LLM domain validation gate, prompt NO_SUITABLE_MATCH, evidence citation

## Files Changed (Overhaul)
- `backend/app/services/dynamic_taxonomy_service.py`
- `backend/app/services/job_taxonomy.py`
- `backend/app/services/department_normalizer.py`
- `backend/app/services/candidate_domain_service.py`
- `backend/app/services/vacancy_service.py`
- `backend/app/services/job_preprocessor.py`
- `backend/app/services/match_service.py`
- `backend/app/services/recommendation_service.py`
- `backend/app/schemas/candidate_context.py`
- `backend/app/schemas/analysis.py`
- `backend/app/schemas/job.py`
- `backend/app/schemas/classification_types.py` (existing, no changes needed)
- `backend/app/prompts/optimized_match.py`
- `backend/app/data/department_domains_seed.json`
- `backend/tests/test_classification_normalization.py` — NEW
- `backend/tests/test_dynamic_taxonomy_evidence.py` — NEW
- `backend/tests/test_cross_domain_guard_db_driven.py` — NEW
- `backend/tests/test_llm_domain_validation.py` — NEW
