# Work Status

## Last Completed Task
**Fix batch CV processing and move matching to Redis/RQ**

### Architecture Impact Analysis
- Replaced synchronous batch matching inside the HTTP request with a persisted RQ batch coordinator and standard per-CV RQ child jobs.
- Batch source CVs now cross the same `UploadService` binary validation and content-addressed retention boundary as individual uploads; PDF/DOCX files are never decoded with `Path.read_text()`.
- Every child job uses the existing `ProcessingQueueService -> process_cv_job -> process_cv_file -> MatchService` chain, preserving the normal parser, identity, caching, retry, persistence, and matching behavior.
- Added a batch-job status endpoint that aggregates durable child-job state and results without re-running matching in the API process.
- The frontend now treats POST as an asynchronous submission and polls the batch job until `COMPLETED`, `COMPLETED_DEGRADED`, or `FAILED`.
- No parser, matching algorithm, Ollama client, vacancy-loading rule, or database schema changed.

### Files Changed
- Batch coordinator API and authorization: `backend/app/api/batch.py`, `backend/app/core/access_policy.py`.
- Batch state contracts and persistence: `backend/app/schemas/batch.py`, `backend/app/repositories/batch_job.py`.
- RQ coordination and child result aggregation: `backend/app/services/batch_processing_service.py`.
- Shared binary upload retention: `backend/app/services/upload_service.py`.
- Frontend asynchronous contract and polling: `frontend/src/types/api.ts`, `frontend/src/services/batchService.ts`, `frontend/src/hooks/useBatchProgress.ts`, `frontend/src/app/batch.tsx`.
- Regression coverage: `backend/tests/test_batch_job_processing.py`, `backend/tests/test_phase6_api_reliability.py`.
- `workstatus.md`.

### Implementation Plan
- Make the batch POST validate only the requested limit, persist a batch record, enqueue one coordinator, and return HTTP 202.
- Discover candidates in the RQ coordinator rather than the HTTP request.
- Load each CV as bounded binary content, validate PDF/DOCX structure, and persist a content-addressed retained copy.
- Submit each candidate through the existing standard CV processing queue.
- Aggregate child processing records and stored match results through a batch status endpoint.
- Update the frontend to poll the persisted batch job and render completed or per-candidate failed results.

### Code Changes
- `POST /api/batch/match-candidates` now returns a queued batch job immediately and returns HTTP 503 if Redis/RQ is unavailable.
- Added `GET /api/batch/jobs/{batch_job_id}` for progress and final results.
- Added `BatchJobRecord`, `BatchJobItem`, and a cache-backed repository using the existing processing-job cache tiers and TTL.
- Added an RQ coordinator that queries MSSQL candidates, validates and retains binary CV content through `UploadService`, and submits deterministic standard CV jobs.
- Coordinator retries are idempotent: already-queued coordinators stop at `cv_jobs_queued`, while child submissions retain the existing content-addressed processing-job identity.
- Batch completion becomes `COMPLETED_DEGRADED` when any source or child job fails or completes degraded.
- Added `UploadService.persist_bytes` and routed individual upload persistence through it so batch and individual inputs share one validation/persistence implementation.
- Removed direct `MatchService.analyze_single_cv` and `Path.read_text()` usage from the batch path.

### Verification Checklist
- [x] Batch PDF/DOCX files are not read with `read_text()`.
- [x] The batch POST performs no candidate query, CV parsing, or matching.
- [x] One RQ coordinator is enqueued and returns immediately.
- [x] Each candidate is submitted through the normal per-CV RQ job and parser/matching pipeline.
- [x] Binary source validation, content limits, safe names, signatures, and retained storage reuse `UploadService`.
- [x] Batch status exposes queued, processing, completed, degraded, and failed outcomes with per-candidate results.
- [x] Coordinator retry coverage verifies child jobs are not submitted twice after `cv_jobs_queued`.
- [x] Language-server diagnostics found no new source errors; unresolved installed-dependency imports remain environment-level diagnostics.
- [x] `git diff --check` passed.
- [ ] Tests and builds were not run because repository instructions require explicit permission.

### Refactoring Performed
- Extracted binary persistence into `UploadService.persist_bytes` so HTTP uploads and MSSQL-discovered batch files share the same validation and retention path.

## Previous Task
**Fix Docker healthcheck and dependency readiness reporting**

### Architecture Impact Analysis
- Replaced the API container's dependency on the absent final-image `curl` binary with a Python-standard-library probe shipped inside the backend image.
- Changed the Docker probe target from the informational root route to `/health` and made the same probe authoritative in production and local Compose.
- `/health` now represents configured MSSQL, PostgreSQL, Redis, and enabled Ollama readiness. It returns HTTP 200 with `status=ok` only when each configured dependency is online or intentionally disabled, and HTTP 503 with `status=unhealthy` otherwise.
- Existing dependency field names remain intact; the response adds a `redis` field.
- No database, queue, LLM client, startup lifecycle, or application route behavior outside health reporting changed.

### Files Changed
- Container healthchecks: `docker-compose.yml`, `docker-compose.local.yml`.
- Image-native probe: `backend/scripts/container_healthcheck.py`.
- Dependency readiness endpoint: `backend/app/main.py`.
- Frontend health contract: `frontend/src/types/api.ts`.
- Regression coverage: `backend/tests/test_phase6_api_reliability.py`.
- `workstatus.md`.

### Implementation Plan
- Use Python already present in the final backend image to call `/health` and validate both HTTP status and JSON status.
- Include Redis in the existing dependency checks without creating another Redis client.
- Derive the overall readiness state from all configured dependencies and return a non-success HTTP status when any is offline.
- Preserve disabled optional dependencies as healthy configuration states.
- Add focused regressions for healthy, database-unavailable, Redis-disabled/unavailable, and enabled-Ollama-unavailable states.

### Code Changes
- Added `scripts/container_healthcheck.py` using only `urllib`, `json`, and `sys`; connection, HTTP, timeout, and invalid-payload failures exit nonzero.
- Both API Compose healthchecks now execute `python scripts/container_healthcheck.py`; no runtime `curl` is required.
- `/health` retains `database`, `pg_database`, and `ollama_llm`, adds `redis`, and returns HTTP 503 when a configured dependency reports offline.
- Redis health reuses the existing centralized cache client and reports `disabled`, `online`, or `offline`.
- Added endpoint regressions covering HTTP status and dependency payload semantics.

### Verification Checklist
- [x] The API container healthcheck no longer invokes `curl`.
- [x] The probe uses Python stdlib available in the final `python:3.12-slim-bookworm` image.
- [x] Production and local Compose probe the same `/health` endpoint.
- [x] Healthy configured dependencies produce HTTP 200 and `status=ok`.
- [x] An unavailable configured dependency produces HTTP 503 and `status=unhealthy` while preserving per-dependency states.
- [x] Redis and enabled Ollama readiness are included; intentionally disabled dependencies do not fail readiness.
- [x] Language-server diagnostics found no new source errors; unresolved installed-dependency imports remain environment-level diagnostics.
- [x] `git diff --check` passed.
- [ ] Tests, builds, and Docker execution were not run because repository instructions require explicit permission.

### Refactoring Performed
- Centralized the Compose HTTP probe in one reusable image-local script and reused the existing Redis and Ollama clients for dependency checks.

## Previous Task
**Fix PostgreSQL result persistence reliability**

### Architecture Impact Analysis
- Added explicit result durability metadata at the existing result-repository boundary: successful PostgreSQL writes are `durable`, while processing success with a failed PostgreSQL write is `degraded`.
- Added `COMPLETED_DEGRADED` as a terminal processing-job state and propagated it through job records, status APIs, response schemas, and the upload UI.
- Kept result identity anchored to the existing deterministic `cv_key` PostgreSQL primary key, so persistence retries update the same logical row rather than inserting duplicate results.
- Existing stored workflow configurations are upgraded in memory with the degraded state and transitions.
- No CV parsing, matching, PostgreSQL schema, Ollama integration, request contract, or successful result behavior changed.

### Files Changed
- Result persistence and retained-source behavior: `backend/app/repositories/result.py`, `backend/app/services/cv_service.py`.
- Job state and workflow compatibility: `backend/app/schemas/contracts.py`, `backend/app/core/rule_config_manager.py`, `backend/app/repositories/processing_job.py`, `backend/app/services/processing_queue.py`.
- API visibility and schemas: `backend/app/api/cv.py`, `backend/app/api/analysis.py`, `backend/app/schemas/cv.py`, `backend/app/schemas/analysis.py`.
- Frontend visibility: `frontend/src/hooks/useCvUpload.ts`, `frontend/src/types/api.ts`.
- Regression coverage: `backend/tests/test_generation_consistency.py`, `backend/tests/test_phase4_background_processing.py`, `backend/tests/test_rule_config_manager.py`.
- `workstatus.md`.

### Implementation Plan
- Annotate every PostgreSQL result-write attempt with durable or degraded persistence state.
- Convert otherwise-completed processing to `COMPLETED_DEGRADED` when PostgreSQL persistence fails while preserving Redis/disk fallback data.
- Surface the degraded terminal state and a safe persistence error through job and result status APIs and the upload UI.
- Preserve retry input and reuse the deterministic result key so a later successful attempt repairs one logical PostgreSQL row.
- Add focused regressions for failure visibility, workflow compatibility, and idempotent retry persistence.

### Code Changes
- `ResultRepository.atomic_save_result` now clears prior degradation before retry, marks successful PostgreSQL persistence as durable, and marks caught PostgreSQL failures as degraded before writing fallback storage.
- The worker persists `COMPLETED_DEGRADED` with a retryable dependency error instead of silently transitioning to `COMPLETED`.
- Status APIs no longer normalize degraded results back to full completion; responses expose `persistence_status` and `persistence_error`.
- Raw-upload cleanup uses the failure-retention policy for degraded persistence, preserving retryability.
- Retry saves continue to query/update by the `CVResult.cv_key` primary key; regression coverage verifies repeated saves produce one row.
- The frontend recognizes degraded completion as terminal and displays a PostgreSQL persistence warning.

### Verification Checklist
- [x] PostgreSQL persistence failure cannot be reported as a fully durable `COMPLETED` result.
- [x] Fallback Redis/disk results carry `COMPLETED_DEGRADED`, `persistence_status=degraded`, and a safe observable error.
- [x] Processing-job state and API responses preserve degraded completion.
- [x] Existing workflow configuration documents are backward-compatible with the new state.
- [x] Raw upload retention supports a later repair attempt.
- [x] Retry writes use the deterministic `cv_key` primary key and regression coverage asserts one logical PostgreSQL row.
- [x] Language-server diagnostics found no new source errors; unresolved dependency imports and existing environment/type diagnostics remain.
- [x] `git diff --check` passed.
- [ ] Tests and builds were not run because repository instructions require explicit permission.

### Refactoring Performed
- Centralized PostgreSQL durability state and the safe persistence error text in `ResultRepository`; no unrelated refactoring was performed.

## Previous Task
**Fix vacancy DB failure handling**

### Architecture Impact Analysis
- Added an explicit vacancy load result at the repository boundary so successful rows, a legitimate successful zero-row query, and stale cached data are distinct states.
- MSSQL session/query failures now raise a source-unavailable error when no successful cached snapshot exists; they are never converted into or cached as an empty vacancy list.
- Existing `GET /api/jobs` list bodies remain backward compatible. The route returns HTTP 503 without a usable cache and exposes `X-Vacancy-Status` for successful, empty, or stale results.
- Existing internal list callers remain compatible; an unavailable source with only an empty stale snapshot raises instead of producing a false no-active-vacancies result.
- No Ollama integration, matching algorithm, vacancy query, or persistence model changed.

### Files Changed
- Vacancy repository state/error handling: `backend/app/repositories/job.py`.
- Vacancy API status propagation: `backend/app/api/jobs.py`.
- Browser-readable response metadata: `backend/app/main.py`.
- Frontend metadata handling: `frontend/src/services/apiClient.ts`, `frontend/src/services/jobsService.ts`, `frontend/src/hooks/useJobs.ts`.
- Frontend vacancy states: `frontend/src/app/index.tsx`, `frontend/src/app/vacancies/index.tsx`.
- Regression coverage: `backend/tests/test_job_repository.py`.
- `workstatus.md`.

### Implementation Plan
- Represent vacancy loads with explicit success, empty, and stale statuses.
- Cache only results returned by a completed MSSQL vacancy query, including legitimate zero-row results.
- Fall back to the last successful cache after MSSQL failure and return HTTP 503 when no usable cache exists.
- Preserve the jobs list response contract and transport freshness through a response header.
- Render MSSQL-unavailable and stale-cache states separately from a legitimate empty vacancy directory.

### Code Changes
- Added `VacancyLoadResult`, `VacancyLoadStatus`, and `VacancySourceUnavailableError` to the existing job repository.
- Changed staleness checks to return an unavailable state on failed DB validation instead of declaring the cache fresh.
- Corrected zero-row staleness comparisons so a real transition from vacancies to zero vacancies refreshes and caches the legitimate empty result.
- Added `X-Vacancy-Status` to `GET /api/jobs` and CORS-exposed headers; source failure without cache now returns HTTP 503.
- Added response-metadata support to the shared frontend client and stale-cache warnings to the dashboard and vacancy directory.
- Added regressions for uncached MSSQL failure, legitimate empty results, and stale-cache fallback without cache overwrite.

### Verification Checklist
- [x] MSSQL session/query failure is not written to the vacancy cache as `[]`.
- [x] A successful MSSQL query returning zero active vacancies is cached and reported as `empty`.
- [x] A failed MSSQL refresh returns the last successful snapshot as `stale` without overwriting it.
- [x] A failed MSSQL load without a usable snapshot returns HTTP 503 instead of `No active vacancies`.
- [x] The existing `GET /api/jobs` JSON list contract is preserved.
- [x] Frontend views distinguish unavailable, stale, legitimate-empty, and successful vacancy states.
- [x] Language-server diagnostics found no new source errors; unresolved backend dependency imports are environment-level diagnostics.
- [x] `git diff --check` passed.
- [ ] Tests and builds were not run because repository instructions require explicit permission.

### Refactoring Performed
- Centralized vacancy freshness/source-state decisions in `JobRepository.load_all_jobs`; existing list-based callers continue through `get_all_jobs`.

## Previous Task
**Connect Add Designation to PostgreSQL taxonomy and pgvector**

### Architecture Impact Analysis
- Connected the existing administrator `POST /api/domain-knowledge/designations` route to a real `DynamicTaxonomyService.add_designation` implementation.
- Designation masters and synonyms are written only to the CV Analyzer-owned PostgreSQL `cvai` taxonomy tables; designation and synonym embeddings are written to PostgreSQL `domain_embeddings` using pgvector.
- The write path does not open, import, update, or flush an MSSQL session. Existing MSSQL taxonomy reads used by classification remain unchanged.
- Reused `DomainEmbeddingService` and the centralized `EmbeddingService` batch generation path; no second Ollama client, retry strategy, cache, or embedding implementation was introduced.
- The route and response contract remain unchanged.

### Files Changed
- Route documentation/error detail: `backend/app/api/domain_knowledge.py`.
- PostgreSQL taxonomy write service: `backend/app/services/dynamic_taxonomy_service.py`.
- Transaction-compatible embedding generation option: `backend/app/services/domain_embedding_service.py`.
- Regression coverage: `backend/tests/test_domain_knowledge_embeddings.py`.
- `workstatus.md`.

### Implementation Plan
- Validate and normalize the designation, parent family, seniority, and synonyms.
- Generate all job-title embeddings through the existing centralized embedding service without independently committing them.
- Resolve the parent job family and add or update the designation and synonyms in PostgreSQL.
- Insert or update the designation/synonym vectors in `domain_embeddings` in the same PostgreSQL transaction.
- Reject missing families, unavailable embeddings, cross-family designation conflicts, and aliases already assigned to another designation.

### Code Changes
- Added `DynamicTaxonomyService.add_designation` with idempotent case-insensitive designation lookup, deterministic designation codes, canonical synonym creation, content hashing, and conflict protection.
- Added `persist_generated` to `DomainEmbeddingService` so callers can reuse centralized generation while owning a larger PostgreSQL transaction; existing callers retain automatic persistence by default.
- Successful Add Designation requests now commit taxonomy and pgvector rows together.
- Corrected the route docstring so it no longer claims to write to MSSQL.
- Added route-delegation and PostgreSQL taxonomy/pgvector persistence regressions.

### Verification Checklist
- [x] `DynamicTaxonomyService.add_designation` now exists and is connected to the route.
- [x] Designations write to `cvai.designations`.
- [x] Canonical names and supplied aliases write to `cvai.designation_synonyms`.
- [x] Corresponding `job_titles` vectors write to PostgreSQL `domain_embeddings`.
- [x] The Add Designation implementation contains no MSSQL session or MSSQL model write path.
- [x] Existing centralized embedding generation remains the only embedding implementation.
- [x] `git diff --check` passed.
- [ ] Tests were not run because repository instructions require explicit permission.

### Refactoring Performed
- Added an opt-out for immediate embedding persistence so taxonomy and vector records can be committed atomically by the PostgreSQL designation service.

## Previous Task
**Make Docker RQ workers consume every project queue through the intended worker entry point**

### Architecture Impact Analysis
- Audited every RQ producer and queue reference in the backend: CV processing, vacancy embedding sync, and upload-directory processing use the configurable `RQ_QUEUE_NAME` (`cv-processing` by default); shadow validation uses `shadow_validation`; the embedding backfill utility references `default`.
- Reused `backend/start_worker.py` as the single worker startup implementation because it already subscribes to the configurable CV queue, `shadow_validation`, and `default` with the existing in-process `SimpleWorker` cleanup behavior.
- Docker production and local workers now use that implementation instead of a separate RQ CLI command that consumed only the CV queue.
- Delayed retry scheduling and the local worker recycle limit remain enabled.
- No RQ producer, job payload, retry policy, queue name, API contract, or Ollama integration changed.

### Files Changed
- Worker implementation and configuration: `backend/start_worker.py`, `backend/app/core/config.py`, `backend/.env.example`.
- Container startup: `docker-compose.yml`, `docker-compose.local.yml`.
- Documentation: `README.md`.
- Regression coverage: `backend/tests/test_cv_status_resolution.py`, `backend/tests/test_worker_cleanup.py`.
- `workstatus.md`.

### Implementation Plan
- Inventory all direct RQ `Queue` construction and enqueue sites.
- Compare producer queue names with the queues consumed by Docker and `start_worker.py`.
- Route both Compose worker services through `start_worker.py`.
- Preserve RQ scheduling and the local maximum-jobs restart behavior in shared settings.
- Update worker tests and startup documentation.

### Code Changes
- Changed both Compose worker commands to `python start_worker.py`.
- Retained the three intended subscriptions and de-duplicated them if `RQ_QUEUE_NAME` is configured as `shadow_validation` or `default`.
- Enabled the RQ scheduler from `start_worker.py`, preserving delayed retry handling previously supplied by the CLI `--with-scheduler` option.
- Added `RQ_WORKER_MAX_JOBS`; zero means unlimited in production, while the lightweight local override retains its default of ten jobs.
- Corrected the queue-configuration regression to mock the worker implementation actually used (`SimpleWorker`) and added recycle-limit coverage.
- Updated manual startup instructions to use the same worker entry point as Docker.

### Verification Checklist
- [x] Configurable primary queue (`cv-processing` by default) is consumed.
- [x] `shadow_validation` is consumed.
- [x] `default` is consumed.
- [x] Production and local Compose use `start_worker.py`; no Compose worker command remains limited to one RQ queue.
- [x] Scheduler support remains enabled for delayed retries.
- [x] Local `RQ_WORKER_MAX_JOBS=10` behavior remains available; production defaults to unlimited.
- [x] `git diff --check` passed.
- [ ] Tests and Docker Compose execution were not run because repository instructions require explicit permission.

### Refactoring Performed
- Consolidated container and manual worker startup on the existing `start_worker.py` implementation and removed the duplicate Compose CLI startup path.

## Previous Task
**Separate CV identity from AIRIS/MSSQL candidate identity in shadow validation**

### Architecture Impact Analysis
- Kept `cv_key` as the document, cache, generation, and matching identity throughout the normal CV pipeline.
- Added a distinct validated `source_candidate_id` for AIRIS/MSSQL-only shadow validation and persisted it through processing jobs and result payloads.
- Manual uploads without an AIRIS candidate ID continue through normal matching with `source_candidate_id=None`; only shadow validation is skipped.
- Existing candidate/CV identity fields and the legacy `MatchService.candidate_id` argument remain backward compatible, but they no longer trigger shadow validation.
- No matching algorithm, role authorization, database model, API response removal, or Ollama integration changed.

### Files Changed
- Identity and processing contracts: `backend/app/core/cv_identity.py`, `backend/app/schemas/contracts.py`.
- Upload, queue, and result propagation: `backend/app/api/cv.py`, `backend/app/api/candidates.py`, `backend/app/services/processing_queue.py`, `backend/app/services/cv_service.py`.
- Matching and shadow flow: `backend/app/services/match_service.py`, `backend/app/services/shadow_validation_service.py`, `backend/app/api/batch.py`.
- Regression coverage: `backend/tests/test_shadow_validation.py`.
- `workstatus.md`.

### Implementation Plan
- Normalize only explicitly supplied AIRIS/MSSQL candidate IDs into positive integers.
- Carry `cv_key` and `source_candidate_id` as independent values across upload, queue, matching, reprocessing, and batch flows.
- Gate shadow validation exclusively on `source_candidate_id` and remove conversion of the CV key.
- Preserve legacy callers while preventing their `candidate_id` cache alias from enabling shadow validation.

### Code Changes
- Added `normalize_source_candidate_id` and exposed the validated value through `CVIdentity.source_candidate_id` and identity metadata.
- Added `source_candidate_id` to `ProcessingJobRecord`, queue submission, worker handoff, interim/final/failure results, cache-hit results, and reprocessing markers.
- Added explicit `cv_key` and `source_candidate_id` inputs to `MatchService`; matching and cache operations now use `cv_key` while shadow enqueue uses only `source_candidate_id`.
- Removed `int(candidate_id)` from the shadow-validation trigger; no CV key is converted to an integer.
- AIRIS batch processing now supplies an explicit source candidate ID, while the shadow worker uses a separate shadow-specific CV key.
- Added regressions proving a numeric-looking CV key does not trigger shadow validation and an explicit source candidate ID does.

### Verification Checklist
- [x] Confirmed there is no `int(cv_key)`, `int(candidate_id)`, or legacy numeric-candidate conversion in the shadow trigger.
- [x] Confirmed manual upload/match paths do not synthesize a source candidate ID from `cv_key`.
- [x] Confirmed AIRIS batch and identified CV upload paths pass the source ID separately.
- [x] Confirmed reprocessing and result-file enrichment preserve the two identities independently.
- [x] Added focused shadow-validation regression coverage.
- [x] `git diff --check` passed.
- [ ] Tests were not run because repository instructions require explicit permission.

### Refactoring Performed
- Centralized source candidate ID normalization in the existing CV identity module and renamed shadow-service boundaries to make their MSSQL identity semantics explicit.

## Previous Task
**Fix organization filters by separating GET query parameters from headers**

### Architecture Impact Analysis
- Changed only the shared frontend HTTP client contract and organization service callers.
- Backend organization routes, query names, response contracts, caching, repositories, and hierarchy validation remain unchanged.
- Authentication headers remain supported independently through the new GET options object.
- No Ollama behavior or integration changed.

### Files Changed
- `frontend/src/services/apiClient.ts`.
- `frontend/src/services/organizationService.ts`.
- `workstatus.md`.

### Implementation Plan
- Add a typed GET options object with separate `params` and `headers` properties.
- Serialize query parameters onto the request URL with URL encoding and null/undefined omission.
- Migrate every organization filter call from a raw second argument to `{ params }`.
- Audit all other `apiClient.get` calls for old positional second-argument usage.

### Code Changes
- Added `ApiQueryValue` and `ApiGetOptions` to the shared client.
- Added centralized query serialization supporting strings, numbers, booleans, repeated array values, existing query strings, and omitted nullish values.
- `apiClient.get(endpoint, options)` now sends `options.params` in the URL and only `options.headers` as HTTP headers.
- Updated company, location, department, and designation organization calls to use `{ params }`.
- Numeric IDs are retained as numbers until centralized serialization, including valid zero values.

### Verification Checklist
- [x] Confirmed backend query names: `business_group_id`, `company_id`, `main_department_id`, and `department_id`.
- [x] Confirmed every organization filter call uses the new `{ params }` contract.
- [x] Audited all frontend `apiClient.get` usages; no other raw positional params/headers caller remains.
- [x] Confirmed the shared GET options type supports params and headers simultaneously.
- [x] `git diff --check` passed.
- [ ] Builds and tests were not run because repository instructions require explicit permission.

### Refactoring Performed
- Centralized query-string construction in `apiClient` rather than duplicating URL assembly in organization services.

## Previous Task
**Connect the frontend configuration screen to the canonical versioned config API**

### Architecture Impact Analysis
- Replaced the frontend's references to the nonexistent legacy `/api/config/match` route with the existing canonical `UnifiedRuleConfig` API.
- Configuration reads now come from `/api/config/active`; writes preserve the complete active document, create a new version, and activate that version through the existing backend workflow.
- Kept the existing frontend form as a view adapter over `scoring.match.scoring_parameters`; no second backend route, repository, schema, or configuration store was introduced.
- Existing administrator authorization for all configuration routes remains unchanged.
- No Ollama client, request, cache, retry, timeout, generation, or embedding behavior changed.

### Files Changed
- Canonical API types and adapter: `frontend/src/types/api.ts`, `frontend/src/services/configService.ts`.
- Configuration UI: `frontend/src/app/config.tsx`.
- Access-policy regression route correction: `backend/tests/test_phase6_api_reliability.py`.
- `workstatus.md`.

### Implementation Plan
- Model the canonical `UnifiedRuleConfig` response and the create/activate responses used by the frontend.
- Map the canonical nested match-scoring parameters into the existing editable form fields.
- On save, fetch the latest active document, merge only submitted match fields, assign a unique version tag, create the full version, and activate it.
- Remove controls for values that are not part of the versioned backend contract.

### Code Changes
- `getMatchConfig` now calls `GET /api/config/active` and reads `scoring.match.scoring_parameters`.
- `updateMatchConfig` now calls `POST /api/config/versions` followed by `POST /api/config/versions/{version_tag}/activate`.
- New versions use `ui-{timestamp}` tags and include frontend creator/audit metadata.
- Unedited configuration sections and unexposed scoring parameters are preserved from the latest active document.
- Removed LLM skip margin/coverage controls because those are runtime environment settings, not fields in `UnifiedRuleConfig`.
- Updated the authorization regression to use the real administrator endpoint `/api/config/active`.

### Verification Checklist
- [x] Live `GET /api/config/active` confirmed the canonical nested match-scoring field names and active version metadata.
- [x] Frontend production code contains no `/api/config/match` reference.
- [x] Frontend configuration calls exactly the three existing backend routes characterized by `access_policy.py`.
- [x] Save construction preserves the complete active configuration and changes only supported match-scoring parameters.
- [x] `git diff --check` passed.
- [ ] Builds and tests were not run because repository instructions require explicit permission.
- [ ] No live save was performed because it would create and activate a persistent configuration version.

### Refactoring Performed
- Consolidated canonical-to-form and form-to-canonical mapping in `configService`; the hook and screen do not duplicate backend document-shape logic.

## Previous Task
**Prevent authentication UI and credentialed-CORS failures when authentication is disabled**

### Architecture Impact Analysis
- Kept `AUTH_ENABLED` as the central backend switch and retained all existing middleware, roles, API keys, and signed-session behavior.
- Made the shared frontend client discover whether authentication is enabled before deciding whether to send browser credentials.
- Authentication-disabled deployments no longer require credentialed CORS merely to bootstrap the frontend.
- No API route, response contract, backend authorization rule, or Ollama behavior changed.

### Files Changed
- `frontend/src/services/apiClient.ts`.
- `frontend/src/components/auth/AuthenticationGate.tsx`.
- `workstatus.md`.

### Implementation Plan
- Query the public session-status endpoint without browser credentials.
- Enable cookie credentials only when the backend reports `auth_required=true`.
- Separate backend-connectivity failures from actual unauthenticated state in the root UI.

### Code Changes
- Replaced unconditional `credentials: 'include'` with a shared credential mode driven by `/api/auth/session`.
- Authentication-disabled mode now uses `credentials: 'omit'` for API calls, so `CORS_ALLOW_CREDENTIALS=false` remains valid locally.
- Authentication-enabled mode performs a credential-free status discovery followed by a credentialed cookie check and retains the existing sign-in/session flow.
- A failed API connection now shows only an API connectivity message and retry action; it no longer displays an access-key prompt before auth status is known.

### Verification Checklist
- [x] Compose resolves `APP_ENVIRONMENT=development` and `AUTH_ENABLED=false` for the local API.
- [x] API and frontend development servers respond on ports 8000 and 8081.
- [x] `GET /api/auth/session` returns HTTP 200 with `authenticated=true` and `auth_required=false`.
- [x] The response permits origin `http://localhost:8081` without requiring credentialed CORS.
- [x] Unauthenticated `GET /api/jobs` returns HTTP 200.
- [x] `git diff --check` passed.
- [ ] In-app browser visual verification was unavailable because the browser-control runtime is not exposed in this session.

### Refactoring Performed
- Centralized frontend credential-mode selection in `apiClient`; screens and feature services remain unaware of authentication details.

## Previous Task
**Make `AUTH_ENABLED` the single authentication enable/disable switch**

### Architecture Impact Analysis
- Kept `AccessControlMiddleware`, endpoint access policies, recruiter/administrator roles, API-key authentication, and signed browser sessions unchanged.
- Changed only the centralized `Settings.AUTH_REQUIRED` decision so deployment environment no longer overrides the explicit authentication switch.
- The frontend already consumes `/api/auth/session`; with authentication disabled it receives `authenticated=true` and renders normally without sign-in.
- No route-specific bypass, localhost condition, API contract change, or Ollama behavior was introduced.

### Files Changed
- Central switch: `backend/app/core/config.py`.
- Compose configuration: `docker-compose.yml`, `docker-compose.local.yml`.
- Regression coverage: `backend/tests/test_phase6_api_reliability.py`.
- Documentation: `README.md`, `workstatus.md`.

### Implementation Plan
- Return `AUTH_ENABLED` directly from `AUTH_REQUIRED`.
- Preserve secure-on defaults in the production Compose file while allowing `.env` overrides.
- Preserve auth-off defaults in the local Compose override while allowing the same `.env` variable to override it.
- Verify protected access with authentication disabled, missing credentials with authentication enabled, and valid credentials with authentication enabled.

### Code Changes
- Replaced `return self.AUTH_ENABLED or self.IS_PRODUCTION` with `return self.AUTH_ENABLED`.
- Changed root Compose to `AUTH_ENABLED: '${AUTH_ENABLED:-true}'`.
- Changed the local Compose override to `AUTH_ENABLED: '${AUTH_ENABLED:-false}'` so it also honors the same environment variable.
- Replaced the obsolete production-forced-auth regression with explicit enabled/disabled behavior tests against `GET /api/jobs`.
- Updated documentation that previously stated production always forces authentication.

### Verification Checklist
- [x] `AUTH_ENABLED=false`: unauthenticated `GET /api/jobs` returns HTTP 200 through the existing central middleware bypass.
- [x] `AUTH_ENABLED=true`: unauthenticated `GET /api/jobs` returns the existing HTTP 401 `UNAUTHORIZED` response.
- [x] `AUTH_ENABLED=true`: `Authorization: Bearer recruiter-secret` successfully accesses `GET /api/jobs`.
- [x] Existing administrator role enforcement and `X-API-Key` authentication coverage also passed.
- [x] Focused result: 3 tests passed, 12 deselected.
- [x] Full operational reliability result: 15 tests passed.
- [x] `git diff --check` passed.
- [x] No authentication middleware, roles, API-key/token support, or individual API routes were removed or bypassed.

### Refactoring Performed
- None; this was the smallest centralized configuration change.

## Previous Task
**Connect the frontend to protected production APIs without embedding an administrator key**

### Architecture Impact Analysis
- Preserved the existing API-key roles and `AccessControlMiddleware` as the authorization authority.
- Added a stateless browser-session adapter: a supplied API key is validated once, then replaced by a short-lived signed HttpOnly cookie for subsequent requests.
- Kept the Expo frontend static; no server credential or `EXPO_PUBLIC_*` secret was introduced.
- The cookie is accepted by the same middleware for HTTP, uploads, and browser WebSocket handshakes; direct API-key authentication remains backward compatible for non-browser clients.
- No Ollama configuration, client, cache, retry, timeout, generation, or embedding path changed.

### Files Changed
- Backend authentication and routing: `backend/app/api/auth.py`, `backend/app/core/security.py`, `backend/app/core/access_policy.py`, `backend/app/core/config.py`, `backend/app/core/lifecycle.py`, `backend/app/main.py`.
- Frontend session flow: `frontend/src/services/apiClient.ts`, `frontend/src/components/auth/AuthenticationGate.tsx`, `frontend/src/app/_layout.tsx`, `frontend/src/components/ui/Sidebar/SidebarLayout.tsx`.
- Configuration, documentation, and regression coverage: `docker-compose.yml`, `backend/.env.example`, `README.md`, `backend/tests/test_phase6_api_reliability.py`.
- `workstatus.md`.

### Implementation Plan
- Characterize the session endpoints explicitly as public while keeping all application routes protected by their existing recruiter/administrator policy.
- Exchange a transient user-entered API key for a role-bearing session signed with an independent server-only secret.
- Store the session only in an `HttpOnly`, `SameSite=Strict`, production-`Secure` cookie and send it with every shared frontend API request.
- Gate application routes on session status, return to sign-in on HTTP 401, and expose an explicit logout action.

### Code Changes
- Added `GET`, `POST`, and `DELETE /api/auth/session` for session inspection, creation, and logout.
- Added HMAC-signed, versioned, expiring session tokens with signature, expiry, format, and role validation.
- Required an independent `AUTH_SESSION_SIGNING_KEY` of at least 32 characters; missing or weak configuration fails browser session creation closed.
- Added `AUTH_SESSION_TTL_SECONDS` with an eight-hour default and credentialed-CORS deployment configuration.
- Updated `apiClient` to use `credentials: 'include'`, centralize session operations, and notify the auth gate when a protected call returns HTTP 401.
- Added a sign-in gate that holds the access key only for the exchange request, clears it immediately afterward, and never persists it in frontend configuration or storage.
- Added role/session display and logout to the existing sidebar.

### Verification Checklist
- [x] Static source inspection confirms no API key or session-signing secret is embedded in frontend code or public environment variables.
- [x] Session cookies are configured `HttpOnly`, `SameSite=Strict`, path-scoped to `/`, and `Secure` in production.
- [x] Session signatures use an independent server-side secret, preserve recruiter/administrator authorization, expire, and reject tampering.
- [x] Direct `Authorization: Bearer` and `X-API-Key` clients remain supported.
- [x] `git diff --check` passed before the work-status update.
- [x] Added focused tests for cookie attributes, key non-disclosure, protected access, administrator denial, logout, expiry, and tampering.
- [ ] Builds and tests were not run because repository instructions require explicit permission.
- [ ] Production deployment must set a unique `AUTH_SESSION_SIGNING_KEY`, the exact HTTPS frontend `ALLOWED_ORIGINS`, and `CORS_ALLOW_CREDENTIALS=true`.

### Refactoring Performed
- Centralized API-key and session-cookie authentication in the existing access-control middleware.
- Centralized frontend session handling in the shared API client and one root authentication gate; individual services and screens did not gain duplicate auth logic.

## Previous Task
**Make CV-to-department and active-vacancy matching fully evidence-driven**

### Architecture Impact Analysis
- Kept `CandidateAnalysisContext`, `CandidateDomainService`, `DynamicTaxonomyService`, `ScoringEngine`, and `VacancyFitEvaluator` as the shared matching pipeline; no candidate-specific branch or second matching engine was introduced.
- Preserved `app.core.config.settings`, `OllamaLLMService`, `OllamaTransport`, `EmbeddingService`, and their existing cache/retry/timeout paths as the only Ollama integration points.
- Active MSSQL vacancy qualifications now flow through `VacancyService` into deterministic scoring and the existing optimized prompt.
- Existing response fields and routes remain backward compatible; one additive vacancy metadata field distinguishes explicit mandatory skills from source-system additional knowledge.

### Files Changed
- Matching context and domain classification: `backend/app/schemas/candidate_context.py`, `backend/app/services/candidate_domain_service.py`, `backend/app/services/dynamic_taxonomy_service.py`.
- Vacancy requirements and scoring: `backend/app/schemas/job.py`, `backend/app/schemas/job_context.py`, `backend/app/services/vacancy_service.py`, `backend/app/services/match_evaluators.py`, `backend/app/services/scoring_engine.py`, `backend/app/services/match_service.py`.
- Configuration and prompt propagation: `backend/app/core/config.py`, `backend/app/core/rule_config_manager.py`, `backend/app/services/configuration_service.py`, `backend/app/prompts/optimized_match.py`.
- Regression coverage: `backend/tests/test_llm_optimization.py`, `backend/tests/test_main_department_classification.py`, `backend/tests/test_organization_hierarchy.py`, `backend/tests/test_two_stage_matching.py`, `backend/tests/test_vacancy_fit_scoring.py`, `backend/tests/test_vacancy_match_status.py`.
- `workstatus.md`.

### Implementation Plan
- Use parsed professional roles, responsibilities, skills, projects, and education as distinct candidate evidence sources.
- Resolve department semantics and all match thresholds/weights from configured taxonomy/scoring data.
- Preserve strong professional matches while surfacing education and upper-experience conflicts for HR review.
- Rank and select openings using the canonical vacancy-fit result and retain strict rejection for explicit hard requirements or verified hierarchy/domain conflicts.

### Code Changes
- Added structured professional evidence to the candidate context and corrected enum-based taxonomy fallback selection.
- Removed the hardcoded internal department/skill semantic map and the hardcoded sparse-maintenance skill inference; department vocabulary now comes from `DepartmentDomainRepository`.
- Replaced hierarchy and vacancy-fit constants with normalized configuration fields and existing scoring-profile weights/thresholds.
- Bumped the centralized matching version to `2.2.0` so prior match/LLM cache entries cannot mask the new behavior.
- Corrected enriched-match propagation so `vacancy_fit_score`, `score_breakdown`, and `vacancy_match_status` are no longer discarded before selection.
- Loaded vacancy/job-profile qualification names in bulk and propagated them as education requirements to scoring and the optimized prompt.
- Marked MSSQL `RequestedAdditionalKnowledge` as scored but non-mandatory because the source provides no mandatory flag; explicit `required_skills_are_mandatory=true` inputs retain hard-failure behavior.
- Changed maximum experience to its existing preferred upper-bound evaluation instead of also applying a duplicate hard seniority rejection.
- Added configured semantic equivalence and inflection-aware matching for wording variants, while retaining explicit evidence and missing-skill reporting.
- Education mismatches now appear as `Education Mismatch (...)`, contribute a zero education component, and require HR review without erasing a verified role/skills/experience match.

### Verification Checklist
- [x] Static source audit found none of the three audit CV IDs in application or test logic.
- [x] Static source audit confirmed removal of the hardcoded department semantic map, maintenance skill inference, seniority buffer, vacancy-fit weights, and evaluator default thresholds.
- [x] `git diff --check` passed.
- [x] Added regression coverage for configured department vocabulary, vacancy qualification propagation, prompt education propagation, advisory education/upper-experience conflicts, and configured vacancy-fit scoring.
- [ ] Builds and tests were not run because repository instructions require explicit permission.
- [ ] Stored audit records require reprocessing before their persisted analysis reflects the new matching version.

### Refactoring Performed
- Consolidated root-family comparison for role, experience, and cross-domain evaluation.
- Normalized scalar-or-list vacancy fields once in `JobEvaluationContext`.
- Reused centralized `DomainEmbeddingService`/`EmbeddingService` for semantic skill equivalence instead of creating an Ollama client or endpoint wrapper.

## Previous Task
**Fix candidate-detail hiring-intelligence column layout**

### Architecture Impact Analysis
- Changed presentation only in the existing candidate detail page.
- Candidate loading, match normalization, recommendation data, API contracts, and Ollama behavior remain unchanged.

### Files Changed
- `frontend/src/app/candidates/[id].tsx`.
- `workstatus.md`.

### Implementation
- Replaced desktop widths totaling 100% plus a gap with proportional `5:7` flex columns, preventing overflow and unintended wrapping.
- Added `min-w-0` and zero flex-basis constraints so both columns can shrink within the available viewport.
- Made the Hiring Intelligence header and AI domain metadata rows wrap safely when badges or values are long.
- Constrained long professional-domain text while retaining right alignment on wider layouts.

### Verification Checklist
- [x] Serena reports no errors or warnings for `frontend/src/app/candidates/[id].tsx`.
- [x] `git diff --check` passed.
- [ ] Browser visual verification was unavailable because the browser-control runtime is not exposed in this session.
- [ ] Builds and tests were not run because repository instructions require explicit permission.

### Refactoring Performed
- Reused the existing cards, badges, spacing tokens, and responsive breakpoint; no new component or CSS rule was introduced.

## Previous Task
**Activate `gemma3:4b` for the Docker backend**

### Architecture Impact Analysis
- Preserved `app.core.config.settings` as the single Ollama configuration source.
- No Ollama transport, generation, embedding, API contract, cache, or scoring logic changed.

### Files Changed
- `.env`: changed the active Compose runtime model from `qwen3:4b` to `gemma3:4b`.
- `backend/.env.example`: already contained `OLLAMA_MODEL=gemma3:4b` from the user's existing changes; no additional edit was required.
- `workstatus.md`.

### Implementation
- Rebuilt and force-recreated the `api` and `worker` services using the merged base and local Compose configuration.
- Confirmed both recreated containers receive `OLLAMA_MODEL=gemma3:4b`.

### Verification Checklist
- [x] API and worker containers are healthy.
- [x] API startup verified the `gemma3:4b` generation model and `nomic-embed-text` embedding model.
- [x] Live `/api/match/health` returns `status=online`, `model_configured=gemma3:4b`, and `model_available=true`.
- [x] `git diff --check` passed.

### Refactoring Performed
- None; this was a configuration-only runtime switch.

## Previous Task
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
# Candidate Hiring Intelligence and Timeline UI Correction (2026-08-10)

## Work completed
- Restored the intended responsive candidate overview split with reliable standard width utilities; the Hiring Intelligence column now fills the remaining desktop width without overflowing.
- Made Hiring Intelligence content consistently stretch and left-align within its card.
- Added recommendation display-text cleanup for OCR bullets, encoded ampersands, repeated whitespace, dangling punctuation, and an empty department phrase.
- Corrected timeline construction so internal assignments remain under one employment period instead of being reported as concurrent/overlapping jobs.
- Added a regression test asserting that an internal deputation produces zero concurrent roles and no concurrent-cluster timeline event.

## Files changed
- `frontend/src/app/candidates/[id].tsx`
- `frontend/src/utils/candidateDetail.ts`
- `backend/app/services/experience_gap_service.py`
- `backend/tests/test_experience_gap_analysis.py`
- `workstatus.md`

## Verification
- `git diff --check` passed.
- Frontend TypeScript diagnostics are clean for both changed frontend files.
- Backend diagnostics only report pre-existing typing/dependency-environment issues outside the changed timeline logic.
- Tests/build were not run because project instructions require explicit user authorization.

## Pending work
- Restart/recreate the backend service to load the Python timeline change, then refresh the candidate page.
- Optional visual browser verification once the browser runtime is available.

## Important decisions
- Internal promotions, transfers, and deputations are not treated as genuine concurrent employment; the existing canonical job renderer continues to show them as nested assignments.
- Existing unrelated model/environment edits and the deleted `ollama-optimization.md` were preserved untouched.
# Limit Suitable Openings on Candidate Detail (2026-08-10)

## Work completed
- Limited the candidate detail page to display the first five ranked `suitable_openings` instead of rendering the complete result collection.
- Capped the normalized candidate-detail `suitable_openings` collection at five so frontend counts and every page-level consumer also receive only five entries.
- Kept the full backend response and vacancy matching behavior unchanged.

## Files changed
- `frontend/src/app/candidates/[id].tsx`
- `frontend/src/utils/candidateDetail.ts`
- `workstatus.md`

## Verification
- Frontend diagnostics checked for the changed candidate page.
- `git diff --check` passed.
- Tests/build were not run because project instructions require explicit user authorization.

## Pending work
- None.

## Important decisions
- The cap is frontend-only and preserves the existing ranking order, so the five highest-ranked suitable openings are shown while the backend retains the full results.
