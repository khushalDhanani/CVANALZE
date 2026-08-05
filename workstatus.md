# Work Status: CV Analyzer Database Architecture Refactoring

## 1. Completed Work

### PR 1 — Fix database contract
- Added `MSSQL_READ_ONLY_URL` and `POSTGRES_APP_URL` to configuration and decoupled `DB_URL`/`PG_DB_URL`.
- Enforced dual database requirements for production mode in `database.py`.

### PR 2 — Permanently disable MSSQL writes
- Removed `migrations/mssql` folder.
- Configured Alembic `env.py` to reject `--dialect mssql`.
- Created robust read-only `before_flush` listeners for `MssqlReadBase`.
- Created robust test coverage proving MSSQL cannot be written to.

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

## 2. Next Steps
- All requested PR steps 1-7 are fully completed.
- Review and deploy architectural changes.

## 3. Important Decisions
- All MSSQL mapping logic strictly delegates to `MssqlReadBase` and all transactional logic delegates to `PostgresAppBase`.
- Taxonomy Classifier now correctly throws `Unknown` / `NO_SUITABLE_MATCH` for unrecognized domains instead of blindly falling back to `General Operations`, enforcing strict DB-backed taxonomy resolutions.
- Enriched analysis results now strictly delimit "verified authoritative matches" from "AI extrapolated career suggestions", resolving pipeline hallucinations.
