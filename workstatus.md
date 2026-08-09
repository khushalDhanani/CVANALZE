# Work Status

## Last Completed Task
**Fix worker processing failures (prompt templates, DepartmentDomainMaster, RQ retries)**

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
