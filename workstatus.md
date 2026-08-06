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

### PR 3 & PR 5 — Repair and Normalize PostgreSQL configuration
- Replaced monolithic JSON configuration blobs with fully normalized relational models: `RuleConfigProfile`, `RuleComponent`, `SystemRule`, `RuleCondition`, `RuleConditionValue`, `RuleThreshold`, `RulePenalty`, `RuleWeight`.
- Applied strict unique constraints across rules, components, thresholds, weights, and penalties.
- Rewrote `ConfigurationService.create_profile` to insert all config dimensions strictly using relational mapping logic.
- Rewrote `RuleConfigManager.load_config` to rebuild the `UnifiedRuleConfig` object purely from database records, eliminating the legacy `rule_config.json` fallback logic.
- Configured application startup to hard fail if no valid configuration can be loaded.
- Modified tests to use an explicitly patched dynamic config test-fixture for unit testing, and fixed SQLite compilation issues involving `JSONB`.

### PR 4 — Implement complete MSSQL repositories
- Migrated legacy `candidate`, `vacancy`, `job-profile`, `qualification`, `domain`, and `workflow` schemas.
- Implemented `get_candidate_aggregate(candidate_id)`, `get_vacancy_aggregate(vacancy_id)`, and `get_job_profile_aggregate(job_profile_id)` leveraging `MssqlReadBase`.



### PR 6 — Correct taxonomy resolution
- Added `FamilyCompatibility` PostgreSQL schema model.
- Removed legacy static rule initialization (`_in_memory_synonyms` and `_ensure_initialized`) from `DynamicTaxonomyService`.
- Rewrote `DynamicTaxonomyService` to fully leverage MSSQL IDs and PostgreSQL aliases, vector lookups, and `FamilyCompatibility` querying.
- Removed default domain/family fallbacks in `TaxonomyClassifier` (`job_taxonomy.py`) and fully migrated to dynamic database matching.
- Rewrote `test_taxonomy_integration.py` mocks to support mocked dynamic DB lookups instead of static rule lookups.
- Verified test suite integration passes successfully.

### PR 7 — Fix no-match responses
- Standardized on a single explicit `MatchStatus` Enum (`DB_MATCH`, `PARTIAL_MATCH`, `NO_SUITABLE_MATCH`, `INSUFFICIENT_EVIDENCE`, `SOURCE_DATA_UNAVAILABLE`).
- Added top-level `match_status` to `EnrichedCandidateAnalysis`.
- Made `best_match` explicitly optional (`Optional[EnrichedJobMatchResult]`) across schemas, dropping the forced initialization of fake jobs.
- Stripped arbitrary `job_id="general"` and `"Solid technical and professional baseline"` fallback assignments from `match_service.py` and `scoring_engine.py`.
- Preserved no-match classification evidence instead of arbitrarily replacing `classification` with `None`.
- Fully decoupled AI career suggestions from the authoritative database classification.
- Strictly enforced that `DB_MATCH` is only returned for genuine active vacancy matches, never derived purely from candidate taxonomy dictionaries.

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

### PR 8 — Implement Source Synchronization and Audit
- Created `backend/app/models/integration.py` defining standard sync constructs (`SyncRun`, `SyncWatermark`, `SyncError`) and payload snapshot tables (`DepartmentSnapshot`, `DesignationSnapshot`, `JobProfileSnapshot`, `CandidateSnapshot`, `VacancySnapshot`).
- Added robust synchronization services (`integration_sync_service.py`) supporting idempotency via payload hashes and tracking source watermarks (using strict `TIMESTAMP WITH TIME ZONE`).
- Structured deactivation logic to mark `is_active=False` when upstream MSSQL records are hard-deleted.
- Created SQL migration `013_create_integration_schema.sql` to explicitly define the synchronization boundaries.

### PR 9 — Implement Real Shadow Validation
- Built `backend/app/models/validation.py` for evaluating CV-Analyzer runs directly against historical AIRIS human decisions (`ShadowValidationResult`, `ValidationMetricsSnapshot`).
- Implemented `ShadowValidationService` providing non-blocking asynchronous validation wrapping the production matching flow via a newly added `SHADOW_MODE_ENABLED` configuration flag.
- Created `DeltaCalculator` and `MetricsEngine` logic to calculate Precision, Recall, False Positive Rates, and False Negative Rates against legacy AIRIS outputs.
- Developed `backend/scripts/run_historical_shadow_validation.py` to trigger bulk audits and emit statistical analysis of historical accuracy.

### PR 10 — Cutover and MSSQL Cleanup
- Delivered complete data migration pipeline (`export_mssql_cvai.py` and `import_pg_cvai.py`) for syncing historic CV payloads into PostgreSQL JSONB.
- Authored Dependency Checks (`check_mssql_dependencies.sql`) to verify no trailing triggers/procedures exist in MSSQL before final schema drop.
- Designed isolated `002_drop_cvai_schema.sql` for deferred cleanup.
- Appended `MSSQL_CUTOVER_COMPLETE` into the config.
- Generated comprehensive `PR10_Output_Report.md` proving fulfillment of PR1-PR10 goals.

## 2. Next Steps
- P1 fixes and absolute data source isolation tasks have been 100% completed.
- We await resolution on local test-environment `pgvector` dependencies for end-to-end automated testing, but runtime python validations pass globally.

### P0 — Restore Executable Runtime
- [x] Verified that `SessionLocal` is fully replaced with `PostgresAppSession` in `RuleConfigManager`.
- [x] Removed legacy `rule_config.json` fallback references from docstrings and comments in `cache_warmer.py` and `job_taxonomy.py`.
- [x] Ensured `ConfigurationService.create_profile` stores the UnifiedRuleConfig using fully normalized PostgreSQL relational rows (e.g., `RuleComponent`, `SystemRule`, `RuleCondition`, etc.) in a single transaction.
- [x] Verified that `_hydrate_profile` in `RuleConfigManager` dynamically reconstructs the config dict solely from these normalized PostgreSQL rows.
- [x] Verified that `ConfigurationService.activate_profile` properly captures `activated_by`, `activated_at`, `activation_reason`, `audit_reason`, and `previous_version_tag`.
- [x] Fixed the argument bug in `run_auto_migrations()` within `app/core/database.py` (switched to explicit keyword arguments: `db_url=settings.POSTGRES_APP_URL`, `dry_run=False`, `dialect="postgres"`).
- [x] Added `tests/test_startup.py` to ensure all models load correctly and `configure_mappers()` runs without error.
- [x] Fixed an import error in `app/models/__init__.py` where `DesignationAbbreviation` was declared in `__all__` but not imported.
- [x] Repaired `api/config.py` to fetch configuration via `RuleConfigManager.get_config().model_dump()` instead of referencing deleted JSON string columns (`global_confidence_tiers_json`, `fields_config_json`, `scoring_rules_json`).
- [x] Fixed `run_auto_migrations` in `database.py` to no longer swallow exceptions, ensuring startup halts gracefully with a loud exception if migrations fail.

### PR4 — Repository Corrections (AIRIS Model Alignments)
- [x] Built `test_repository_contracts.py` utilizing a mocked SQLAlchemy Session to execute queries safely, catching any references to undeclared schema properties via native `AttributeError`.
- [x] Implemented `test_models_configure_mappers()` and explicit `hasattr()` validation blocks for all models used in repositories.
- [x] **Candidate Aggregates:** Verified `CandidateSkillIsActive` was correctly mapped to `IsActive`. 
- [x] **Vacancy Aggregates:** Verified unsupported active/deleted metadata fields against qualifications were removed, strictly asserting `RequriedQualificationID`.
- [x] **Job Profile Aggregates:** Verified exact attribute access for `OrgJobProfileQualificationDet` (`QualificationIsDeleted`) and `JobProfileDomainKnowledgeDet` (`DomainKnowlgID`, `JobProfileDomainKnowledgeDetIsActive`).

### PR5 and PR6 — MSSQL Aggregate Completion
- [x] **Candidate Aggregate:** Rewrote `get_candidate_aggregate` to use `.outerjoin` blocks against `OrgJobProfileMst`, `RecruitDomainKnowledgeMst`, `RecruitSkillMst`, `LanguageMst`, and `OrgLocationMst`. The payload now returns a fully structured nested dictionary for `experiences`, `qualifications`, `skills`, `languages`, `locations`, `notice_period`, and `domain_knowledge` instead of raw detached IDs.
- [x] **Vacancy Aggregate:** Rewrote `get_vacancy_aggregate` to fetch related taxonomic descriptions by explicitly joining `TransactionStatusMst` (for `RequestStatusID` and `VacancyReqStatusID`), `QualificationMst`, `RecruitDomainKnowledgeMst`, and `RecruitCandidateMst`. Output now includes embedded `candidate_applications`, `request_track`, `candidate_history`, `required_qualifications`, and `job_profile.domains`.
- [x] **Job Profile Aggregate:** Rewrote `get_job_profile_aggregate` to natively `.outerjoin` `OrgCompanyMst`, `OrgDepartmentMst`, and `OrgDesignationMst`, converting them into structured sub-dictionaries (`company`, `department`, `designation`). Joined `QualificationMst` and `RecruitDomainKnowledgeMst` to resolve name fields.

### PR6 and PR7 — Taxonomy Enforcement and Isolation
- Replaced the memory-heavy `get_all_designations` loop inside `DynamicTaxonomyService` with an optimized PostgreSQL indexed lookup (`session.query().filter(ilike())`) directly mapped against `OrgDesignationMst`.
- Downgraded aliases and semantic vector classification to `MatchStatus.PARTIAL_MATCH`. Isolated `MatchStatus.DB_MATCH` strictly to exact MSSQL source identifier matching.
- Permanently deleted `_get_default_fallback` from the taxonomy stack, eliminating the legacy `General Operations` domain hallucination.
- Rewrote the match status termination logic in `analyze_single_cv` inside `MatchService` to aggressively return `MatchStatus.NO_SUITABLE_MATCH` for any candidate failing the active vacancy filter.
- Enforced complete nullification of `recommended_department`, `professional_domain`, `primary_department`, and `best_match` when no active vacancy corresponds to the candidate, ensuring non-authoritative AI career advice is corralled safely into the `ai_career_suggestions` block instead.

### PR9 — Shadow Validation Rewrite
- Completely eliminated unmanaged `threading.Thread` utilization from `MatchService`, ensuring background workload execution does not compromise HTTP worker bounds.
- Re-routed all Shadow Validation requests through the native `RQ` infrastructure (`shadow_validation` queue) wrapped with automated durable persistence / `Retry(max=3)` policies.
- Decoupled `ShadowValidationService` into two distinctly versioned pipelines: the HTTP response executes the production iteration natively, while `execute_shadow_pipeline` initializes a fresh, non-mutating instance of `MatchService.analyze_single_cv`.
- Connected the `AirisHistoricalBenchmark` table directly into `ShadowEvaluator.evaluate`, mapping MSSQL status IDs to authoritative `is_hired` states in real time, rather than relying on hardcoded integer mocks (`[4, 5, 6, 7]`).
- Architected explicit True Positive (TP), True Negative (TN), False Positive (FP), and False Negative (FN) calculations inside `MetricsEngine`, and built concrete algorithmic definitions for Precision, Recall, FPR, and FNR natively logged to `ValidationMetricsSnapshot`.

### P1 — Pre-Integration Fixes
- **Candidate Snapshot Allowlist:** Implemented an explicit column allowlist via `serialize_payload` inside `CandidateSyncService` to prevent the unauthorized duplication of personal identifiable information (PII) like names, emails, and phone numbers into the PostgreSQL integration cache.
- **Partial Failure & Watermark Repair:** Restructured the `run_sync` block to sequentially `.order_by` timestamp and evaluate every row insertion through nested PostgreSQL transactions (`pg_db.begin_nested()`). This allows valid rows to commit while safely pausing the `lowest_failed_timestamp` watermark before a broken row, guaranteeing recovery and preventing total batch drops.
- **Taxonomy Validation & Fallbacks:** Purged `_get_default_fallback` from the codebase.
- **Shadow Threads to RQ:** Converted the last standing instances of unmanaged threads into robust `execute_shadow_pipeline` background RQ workers.

## 3. Important Decisions
- All MSSQL mapping logic strictly delegates to `MssqlReadBase` and all transactional logic delegates to `PostgresAppBase`.
- Taxonomy Classifier now correctly throws `Unknown` / `NO_SUITABLE_MATCH` for unrecognized domains instead of blindly falling back to `General Operations`, enforcing strict DB-backed taxonomy resolutions.
- Enriched analysis results now strictly delimit "verified authoritative matches" from "AI extrapolated career suggestions", resolving pipeline hallucinations.
- Added a non-blocking background thread `ShadowValidationService` in `match_service.py` to seamlessly audit CV Analyzer decisions against historical AIRIS outputs without stalling production API latency.
