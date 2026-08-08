# Work Status

## Last Completed Task
**Fix Docker stack not starting locally**

### Root Cause
Local Postgres volume was completely empty (no schema, no migrations), and the API
requires an active rule-config profile in PostgreSQL on startup. Several latent bugs
also blocked a fresh setup.

### Fixes Applied
1. **`backend/scripts/migrations/postgres/018_add_generation_sequence_column.sql`** —
   table references were unqualified (`cv_results`); migration 011 creates `cvai.cv_results`,
   so 018 failed on fresh DBs. Qualified with `cvai.`. Also fixed the down script
   (`DROP COLUMN IF NOT EXISTS` syntax error + unqualified index/table refs).
2. **New migration `019_widen_system_rules_target_value.sql`** — `cvai.system_rules.target_value`
   was `VARCHAR(255)` but the model uses `Text`; rule metadata (recommendations,
   section_patterns, canonical_equivalents) exceeds 255 chars and seeding failed.
3. **`docker-compose.yml`** — `migrate-postgres` service passed stale `--dialect postgres`
   flag to `run_migrations.py`, which no longer accepts it.
4. **`backend/app/services/configuration_service.py`** — `_broadcast_invalidation` called
   non-existent `RedisCache._get_client()`; replaced with the established `_REDIS_CLIENT` pattern.

### Setup Performed (fresh local DB)
- Ran all migrations via `docker compose -f docker-compose.yml -f docker-compose.local.yml run --rm --build migrate-postgres`.
- Seeded + activated rule-config profile v1.1.0 from `tests/mock_rule_config.py`
  (repo `rule_config.json` was deleted in commit `bcd0c91`; `MOCK_RULE_CONFIG` is the canonical source)
  via `ConfigurationService.create_profile` + `activate_profile`, mounting the mock file into a one-off `api` container.

### Verification
- All containers healthy: `cv_analyzer_api`, `cv_analyzer_worker`, `cv_analyzer_redis`, `cv_analyzer_pgvector`.
- `GET /` -> 200; `GET /api/config/active` returns version 1.1.0 (4 fields, 14 vacancy rules).
- Worker listening on `cv-processing` queue.
- Note: MSSQL write-permission warning is non-fatal in development mode
  (`APP_ENVIRONMENT=development` from `docker-compose.local.yml`).

## Previous Tasks
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
