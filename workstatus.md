# Work Status: CV Analyzer Database Architecture Refactoring

## 1. Completed Work

### PR 1 — Fix database contract
- Added `MSSQL_READ_ONLY_URL` and `POSTGRES_APP_URL` to configuration and decoupled `DB_URL`/`PG_DB_URL`.
- Enforced dual database requirements for production mode in `database.py`.
- Updated scripts (`run_migrations.py` and `verify_schema_drift.py`) and documentation to enforce that migrations target PostgreSQL only.

### PR 2 — Permanently disable MSSQL writes
- Removed `migrations/mssql` folder.
- Configured Alembic `env.py` to reject `--dialect mssql`.
- Created robust read-only `before_flush` listeners for `MssqlReadBase`.
- Intercepted raw SQL queries via SQLAlchemy `before_cursor_execute` to permanently block DML and DDL.
- Added strict internal guards to `run_migrations.py` to reject any execution of the `mssql` dialect.
- Validated application startup to immediately throw a `RuntimeError` if the configured MSSQL account contains any write permissions.
- Created robust test coverage proving MSSQL cannot be written to via ORM, raw text, or migration runner.

### PR 3 — Repair configuration loading
- Replaced non-existent `SessionLocal` with `PostgresAppSession` in `RuleConfigManager`.
- Removed legacy `rule_config.json` file-fallback loading logic.
- Configured application startup to hard fail if no PostgreSQL rule configuration exists.

### PR 4 — Implement complete MSSQL repositories
- Migrated legacy `candidate`, `vacancy`, `job-profile`, `qualification`, `domain`, and `workflow` schemas.
- Implemented `get_candidate_aggregate(candidate_id)`, `get_vacancy_aggregate(vacancy_id)`, and `get_job_profile_aggregate(job_profile_id)` leveraging `MssqlReadBase`.

### PR 5 — Normalize PostgreSQL configuration
- Replaced monolithic JSON configuration blobs with 6 relational models: `RuleConfigProfile`, `RuleConfigRule`, `RuleConfigCondition`, `RuleConfigThreshold`, `RuleConfigPenalty`, `RuleConfigWeight`, `RuleConfigComponent`.
- Upgraded `RuleConfigManager` caching and serialization logic.

### PR 6 — Correct taxonomy resolution
- Added `FamilyCompatibility` PostgreSQL schema model.
- Removed legacy static rule initialization (`_in_memory_synonyms` and `_ensure_initialized`) from `DynamicTaxonomyService`.
- Rewrote `DynamicTaxonomyService` to fully leverage MSSQL IDs and PostgreSQL aliases, vector lookups, and `FamilyCompatibility` querying.
- Removed default domain/family fallbacks in `TaxonomyClassifier` (`job_taxonomy.py`) and fully migrated to dynamic database matching.
- Rewrote `test_taxonomy_integration.py` mocks to support mocked dynamic DB lookups instead of static rule lookups.
- Verified test suite integration passes successfully.

### PR 7 — Fix no-match responses
- Added top-level `match_status` to `EnrichedCandidateAnalysis`.
- Stripped arbitrary `"General"`, `"General Role"`, and `"General Operations"` fallback assignments from `match_service.py`, `scoring_engine.py`, `candidate_domain_service.py`, and `taxonomy_service.py`.
- Separated DB matches from AI suggestions: `classification` is now explicitly set to `null` if the candidate does not produce a `DB_MATCH` (preserving strict integrity), while AI career suggestions are kept distinctly in `ai_career_suggestions`.
- Guaranteed explicit `NO_MATCH` fallback strings across all pipelines when insufficient evidence is found.

### PR 8 — P1 Integration Stability
- Removed hardcoded taxonomy bootstrapping logic and default seeds.
- Removed keyword seeds from `005_create_department_domain_master.sql`.
- Added `mssql_department_id` and `mssql_designation_id` to PostgreSQL taxonomy mappings and created migrations.
- Normalized vocabulary: changed `NO_SUITABLE_MATCH` to `NO_MATCH`.
- Replaced the hardcoded `0.3` fallback in family compatibility checks with a strict `0.0`.
- Eliminated fake values in `_empty_job_match()` and `_empty_analysis()` inside MatchService.
- Designed `SyncService` to automate MSSQL-to-PostgreSQL synchronization.
- Escaped startup warning to raise a `RuntimeError` if MSSQL write permissions are detected.

### PR 9 — Strict Data Source Isolation & Persistence
- Permanently deleted `app/core/jobs.py` and `DEFAULT_JOB_OPENINGS`.
- `JobRepository` now explicitly returns `[]` instead of relying on a fake fallback JSON array.
- Created `CVResult` SQLAlchemy model corresponding to a new `cvai.cv_results` PostgreSQL table.
- Added `011_create_cv_results_table.sql` migration script to execute the new schema.
- Completely rewrote `ResultRepository` to exclusively store and retrieve CV analysis payloads to/from PostgreSQL JSONB columns, purging the legacy `.json` disk caching mechanism inside `uploads/results/`.
- Removed `_cv_file_cache` to guarantee no disk I/O leaks for match results.

## 2. Next Steps
- P1 fixes and absolute data source isolation tasks have been completed.
- Validate end-to-end integration flows against the strict unconfigured taxonomy and PostgreSQL-backed CV result storage.

## 3. Important Decisions
- All MSSQL mapping logic strictly delegates to `MssqlReadBase` and all transactional logic delegates to `PostgresAppBase`.
- Taxonomy Classifier now correctly throws `Unknown` / `NO_SUITABLE_MATCH` for unrecognized domains instead of blindly falling back to `General Operations`, enforcing strict DB-backed taxonomy resolutions.
- Enriched analysis results now strictly delimit "verified authoritative matches" from "AI extrapolated career suggestions", resolving pipeline hallucinations.
