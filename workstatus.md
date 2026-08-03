# Work Status

## Last Updated
2026-08-03T14:50:58+05:30

## Current Task — Phase 7 Documentation and Final Verification
- Replaced the stale minimal README with the implemented Phase 0–6 architecture, actual `backend/` layout, supported-format matrix, request and processing flow,
  access model, canonical job states, stable error envelope, and compatibility behavior.
- Documented every operator-facing setting from `backend/.env.example`, grouped across runtime/access, databases/Redis/RQ, secure uploads, and Ollama/embeddings.
- Added local API and RQ worker startup, explicit PostgreSQL/MSSQL migration commands, Docker Compose production startup order, shared-volume requirements,
  health/OpenAPI locations, and an authorization-gated final verification command set.
- Added a cumulative implementation change map and explicit preserved-surface versus intentional-containment compatibility summary.
- Documented residual limitations for OCR quality, encrypted documents, uncommon layouts, LLM nondeterminism, Ollama availability, malware scanning, rate limiting,
  authorization granularity, PII lifecycle, shared storage, and stale-job recovery.
- Added `backend/docs/phase7-documentation-and-final-verification.md` with the final changed-area map, compatibility assessment, environment/deployment reconciliation,
  residual risk register, verification status, and release checklist.
- Reconciled documentation claims statically against configuration, Compose, Dockerfile, access policy, job/error contracts, upload validation, lifespan, and phase records.
- Confirmed every active environment-template variable is documented, every relative README link resolves, changed Markdown respects the practical line-length rule,
  and tracked-file diff whitespace checks pass.
- Per repository instructions, did not run the application, tests, Ruff, builds, dependency restore, migrations, Docker services, or external services.

## Files Created / Modified for Current Task
- Created: `backend/docs/phase7-documentation-and-final-verification.md`.
- Modified: `README.md`, `workstatus.md`.
- No production or test source file changed in Phase 7.

## Pending Work
- With explicit authorization, run the backend test suite, Ruff, schema-drift verification, Docker Compose validation/build, and target-environment smoke tests listed
  in the README.
- Complete the release checklist in the Phase 7 document, including credential rotation, non-default database secrets, migrations, model availability, ingress
  containment, malware scanning, PII governance, monitoring, shared storage, and stale-job recovery.
- Revalidate downstream clients against the intentional containment changes: PDF/DOCX-only uploads, collision rejection, production authorization, safe body limits,
  sanitized polling failures, and default unknown-job HTTP 404.

## Important Decisions
- Phase 7 is documentation-only; it does not alter API, processing, storage, cache, authorization, or deployment behavior.
- Current source/configuration and the Phase 0–6 records are authoritative where the codebase knowledge graph or old README is stale.
- The root README is the primary operator/developer entry point; detailed rationale and historical compatibility remain in the phase documents and `workstatus.md`.
- Runtime verification is explicitly pending because repository policy prohibits tests, lint, builds, migrations, and service startup without user authorization.
- Compatibility documentation distinguishes additive preserved surfaces from intentional security/correctness changes instead of describing all changes as transparent.

## Previous Task — Phase 6 API and Operational Reliability
- Added centralized request context with safe caller-provided/generated request and correlation IDs, response headers, structured request logging, and JSON size prechecks.
- Activated the Phase 0 access policy through API-key authentication and hierarchical recruiter/administrator authorization for HTTP and WebSocket routes.
- Made production/staging fail closed even if the local-development authentication toggle is disabled; public `/` and `/health` remain available.
- Added a stable canonical error envelope for HTTP, validation, authorization, rate-limit, oversized-body, framework 404, and unexpected failures while retaining legacy `detail`.
- Kept exception traces in server logs with request/correlation context and removed traceback persistence/exposure from both polling aliases and background job adapters.
- Added raw CV text and HR feedback length limits plus safe validation details that never echo submitted values.
- Added a bounded, thread-safe per-process sliding-window rate limiter with HTTP 429, `Retry-After`, and rate-limit headers.
- Replaced wildcard CORS defaults with explicit trusted origins, enumerated methods/headers, disabled credentials by default, and ignored configured wildcard values.
- Replaced startup/shutdown event decorators and import-time schema mutation with one FastAPI lifespan owner for local initialization, dependency checks, warmup, and Ollama cleanup.
- Prevented production/staging startup initialization and automatic migrations regardless of flags; production migration execution is now an explicit release operation.
- Added explicit PostgreSQL pgvector/embedding-table and MSSQL system-configuration migrations for schema previously supplied by startup `create_all()`.
- Aligned Compose on `PG_DB_URL`, one shared API/worker/migration environment, configurable queue name, explicit migration service, health/readiness checks, and Linux host Ollama routing.
- Pinned the backend image to Python 3.12 Bookworm and added Microsoft ODBC Driver 18 plus PDF/OCR runtime libraries.
- Added focused Phase 6 regressions for concrete policy resolution, authentication/roles, production fail-closed behavior, request IDs, safe 500/404/validation errors,
  JSON/field limits, rate limiting, polling traceback scrubbing, trusted CORS configuration, and production schema containment.
- Added `backend/docs/phase6-api-operational-reliability.md` and linked it from the README.
- Audited the Ollama lifecycle path and continued using the centralized `OllamaLLMService`; no request transport, retry, timeout, payload, model, or cache logic changed.
- Per repository instructions, did not run the application, tests, linting, builds, dependency restore, migrations, Docker services, or external services.

## Files Created / Modified for Current Task
- Created reliability core: `backend/app/core/request_context.py`, `backend/app/core/security.py`, `backend/app/core/rate_limit.py`,
  `backend/app/core/error_handlers.py`, `backend/app/core/lifecycle.py`.
- Created migrations: `backend/scripts/migrations/postgres/007_create_vector_embeddings.sql`,
  `backend/scripts/migrations/postgres/007_create_vector_embeddings_down.sql`, `backend/scripts/migrations/mssql/007_create_system_config.sql`,
  `backend/scripts/migrations/mssql/007_create_system_config_down.sql`.
- Created tests/docs: `backend/tests/test_phase6_api_reliability.py`, `backend/docs/phase6-api-operational-reliability.md`.
- Modified core/contracts: `backend/app/core/config.py`, `backend/app/core/access_policy.py`, `backend/app/core/database.py`,
  `backend/app/schemas/contracts.py`, `backend/app/schemas/cv.py`, `backend/app/schemas/analysis.py`.
- Modified app/processing: `backend/app/main.py`, `backend/app/api/analysis.py`, `backend/app/api/cv.py`, `backend/app/api/batch.py`,
  `backend/app/services/cv_service.py`, `backend/app/services/processing_queue.py`.
- Modified deployment/docs/status: `backend/.env.example`, `backend/Dockerfile`, `docker-compose.yml`, `README.md`, `workstatus.md`.

## Pending Work
- Run focused Phase 6 tests, the broader backend suite, Ruff, Docker Compose configuration validation, Docker image build, and lifecycle/auth smoke tests only when explicitly authorized.
- Generate unique recruiter and administrator keys in the deployment secret manager; production intentionally returns HTTP 503 for protected endpoints until keys exist.
- Enforce a shared rate limit at ingress when running multiple API replicas; the application limiter is deliberately per process.
- Provide browser/WebSocket authentication through a trusted same-origin gateway or session-capable proxy rather than exposing API keys in frontend code or query strings.
- Replace the Compose development-default PostgreSQL password and complete the Phase 0 external credential rotation before production deployment.

## Important Decisions
- The Phase 0 access-policy table is the single authorization source; uncharacterized `/api/*` routes fail closed as administrator-only.
- Administrator keys inherit recruiter permissions. Keys are accepted through Bearer authorization or `X-API-Key`, compared in constant time, and never logged.
- Development auth can be disabled for backward-compatible local tests; production/staging auth cannot be disabled through configuration.
- Canonical error responses include additive legacy `detail`; successful response bodies and compatibility aliases remain unchanged.
- Validation responses contain only field location/type/message and never the rejected CV or feedback value.
- `error_details` remains in polling schemas only as a compatibility field and is always returned as `null`.
- Health/root remain public; Docker uses the fast root endpoint for liveness while `/health` retains dependency status reporting.
- Local schema initialization remains available through lifespan. Production schema changes require the migration runner and are never triggered by application import/startup.
- Application rate limits use the socket peer address and never trust forwarded headers; proxied or replicated deployments need an authoritative gateway limit.
- CORS wildcard values are ignored rather than accepted, and credentialed cross-origin requests are opt-in.

## Previous Task — Phase 5 Standardize Ollama
- Added `OllamaTransport` as the only Ollama HTTP boundary for generation, embeddings, tags, and explicit unload operations.
- Added one process-level pooled `httpx.Client` with configurable connection and keep-alive limits.
- Centralized generation, embedding, and unload payload construction; Ollama response envelopes; structured JSON extraction; Pydantic validation error mapping;
  exponential retry/backoff; operation logging; and aggregate/per-operation transport metrics.
- Applied `OLLAMA_REQUEST_TIMEOUT` and `OLLAMA_MAX_RETRIES` uniformly across every Ollama operation and removed hard-coded embedding timeouts.
- Routed every structured generation method through one `OllamaLLMService` executor while preserving the legacy public method names, arguments, schemas, cache behavior,
  profiler metadata, and fallback return types.
- Kept `EmbeddingService` as the sole embedding boundary and routed both single and batch requests through the shared transport after existing cache lookups.
- Mapped connection, timeout, HTTP, missing-model, malformed response, and schema-validation failures to typed Ollama errors.
- Replaced per-CV model unloads with configured request keep-alive and optional process-shutdown unload; the shared HTTP pool always closes at shutdown.
- Extended startup verification to check each enabled generation/embedding model through the shared tags request.
- Added Ollama transport metrics additively to the existing cache analytics response.
- Repaired legacy Ollama tests to target the shared transport and added focused Phase 5 regressions for pooling, cache hits, retries, timeouts, invalid JSON,
  schema failures, unavailable models, embedding delegation, keep-alive/unload, and disabled-LLM fallback.
- Added `backend/docs/phase5-standardize-ollama.md`, linked it from the README, and documented all new environment settings.
- Audited all Ollama integrations before editing; no direct Ollama HTTP client remains outside the shared transport.
- Per repository instructions, did not run the application, tests, linting, builds, dependency restore, migrations, Docker services, or external services.

## Files Created / Modified for Current Task
- Created: `backend/app/services/ollama_transport.py`, `backend/tests/test_phase5_ollama_standardization.py`,
  `backend/docs/phase5-standardize-ollama.md`.
- Modified service/lifecycle integration: `backend/app/services/llm_service.py`, `backend/app/services/embedding_service.py`,
  `backend/app/services/cv_service.py`, `backend/app/main.py`.
- Modified API/configuration: `backend/app/api/analysis.py`, `backend/app/api/analytics.py`, `backend/app/core/config.py`, `backend/.env.example`.
- Modified deployment/tests/docs/status: `docker-compose.yml`, `backend/tests/test_qwen_llm_service.py`, `README.md`, `workstatus.md`.

## Pending Work
- Run the focused Phase 5 tests, broader backend suite, Ruff, and an application lifecycle smoke test only when explicitly authorized.
- Audit external consumers of `extract_candidate_profile`, `call_qwen`, `call_qwen_dynamic`, `unload_model`, and `_get_httpx_client` before removing those compatibility surfaces.
- Size the connection pool, timeout, retry count, backoff, and keep-alive for production Ollama concurrency and model memory constraints.
- Continue Phase 0 pending credential rotation and future access-policy enforcement.

## Important Decisions
- `OLLAMA_MAX_RETRIES` now unambiguously means retries after the initial attempt; the default of `1` permits at most two total attempts.
- HTTP 404 for a model-scoped request is a non-retryable unavailable-model error; HTTP 408, 429, and 5xx responses are retryable.
- Generation schema/JSON failures are retryable within the common policy and fall back to the existing `None` contract after exhaustion.
- `LLM_ENABLED=false` preserves the prior semantic-analysis fallback and bypasses both generation cache access and Ollama transport calls.
- Cached generation and embedding data remain owned by `LLMCacheRepository` and `EmbeddingService`; the transport owns only HTTP concerns and transport metrics.
- Normal processing keeps models resident according to `OLLAMA_KEEP_ALIVE`; unload is an explicit compatibility/lifecycle operation, not a per-CV cleanup step.
- Ollama unload is server-global, so the shutdown unload remains disabled by default and must be coordinated in multi-process API/RQ deployments.
- Existing API paths and response fields remain compatible; `system_stats.ollama_transport` is additive.

## Previous Task — Phase 4 Reliable Background Processing
- Replaced direct FastAPI-only upload execution with one shared Redis/RQ submission service for `/api/cv/upload`, `/api/match/upload`, and candidate reprocessing.
- Added persisted processing-job records before enqueue, including canonical `QUEUED`, `PROCESSING`, `RETRYING`, `COMPLETED`, and `FAILED` transitions.
- Added content-addressed job identity using canonical CV key, source SHA-256, parser version, and schema version.
- Added idempotent duplicate submission handling plus Redis distributed submission/execution locks and local development locks.
- Changed RQ payloads to contain only the job ID; workers reload, structurally revalidate, and hash-check retained raw sources before invoking `process_cv_file`.
- Added configurable RQ timeouts, result retention, retries, retry intervals, processing-record TTLs, and distributed-lock leases.
- Added an explicit development-only in-process fallback with the same persisted state/retry lifecycle; production returns HTTP 503 when Redis/RQ is unavailable.
- Preserved lowercase legacy processing responses while adding `job_id`, `job_state`, `execution_mode`, and `retry_count` fields.
- Changed unknown polling IDs to HTTP 404 by default, with a configurable ISO-8601 compatibility deadline for the former synthetic processing response.
- Preserved and strengthened the reprocessing invariant that retained source availability/validity is checked before prior result or cache invalidation.
- Added a Docker Compose RQ worker with shared uploads storage, Redis dependency health, worker health, and restart configuration.
- Added focused Phase 4 regressions for persistence-before-enqueue, duplicate and changed-content isolation, development/production Redis outage behavior,
  worker source validation, completion/retry transitions, unknown-job 404s, and reprocessing containment.
- Added `backend/docs/phase4-reliable-background-processing.md` and linked it from the README.
- Audited the downstream Ollama path and retained the existing centralized `OllamaLLMService`; no LLM client, retry, timeout, model, or cache logic was duplicated.
- Per repository instructions, did not run the application, tests, linting, builds, dependency restore, migrations, Docker services, or external services.

## Files Created / Modified for Current Task
- Created: `backend/app/repositories/processing_job.py`, `backend/app/services/processing_queue.py`,
  `backend/tests/test_phase4_background_processing.py`, `backend/docs/phase4-reliable-background-processing.md`.
- Modified core/contracts: `backend/app/core/config.py`, `backend/app/core/cache.py`, `backend/app/schemas/contracts.py`,
  `backend/app/schemas/cv.py`, `backend/app/schemas/analysis.py`.
- Modified API/worker integration: `backend/app/api/cv.py`, `backend/app/api/analysis.py`, `backend/app/api/candidates.py`,
  `backend/app/services/cv_service.py`.
- Modified deployment/tests/docs: `docker-compose.yml`, `backend/.env.example`, `backend/requirements.txt`,
  `backend/tests/test_upload_service.py`, `README.md`, `workstatus.md`.

## Pending Work
- Run the focused Phase 4 tests, broader backend suite, Ruff, and Docker Compose configuration validation only when explicitly authorized.
- Choose and deploy a temporary `JOB_NOT_FOUND_COMPATIBILITY_UNTIL` value only if existing clients still depend on synthetic unknown-job responses.
- Add an operational reconciler for jobs left `QUEUED` or `PROCESSING` after a full Redis/worker outage if deployment requirements demand automatic stale-job recovery.
- Continue Phase 0 pending credential rotation and future access-policy enforcement.

## Important Decisions
- Job identity is content- and extraction-version-addressed; supplied candidate/CV identity remains authoritative through the Phase 2 canonical CV key.
- Processing records are written to both Redis and the shared file tier so API/worker startup timing cannot hide a persisted job.
- Raw CV bytes are not placed in Redis; the worker must recover and revalidate the retained source file.
- Production never silently falls back to FastAPI background execution; the fallback is both environment-gated and visible in response metadata.
- Existing `status="processing"` consumers remain compatible while canonical job state is additive.
- Unknown jobs return HTTP 404 when the optional compatibility deadline is absent or expired.
- Reprocessing source validation remains before cache/result invalidation, and workers repeat source validation before execution.
- Ollama generation remains centralized in `OllamaLLMService` and is invoked only through the existing CV/match pipeline.

## Previous Task — Phase 3 Strengthen Structured CV Processing
- Reduced `document_parser.py` to a compatibility façade while moving document conversion, text normalization, deterministic field extraction,
  resume normalization, and quality metrics into focused service modules.
- Added typed normalized resume schemas for contacts, skills, education, employment intervals, and experience validation.
- Added raw values, normalized values, confidence, and evidence while preserving every existing legacy `resume_json` field.
- Normalized email casing/whitespace, compacted phone representation while retaining the original, canonicalized skill aliases,
  normalized education degree/domain/institution fields, and added employment date intervals/durations.
- Made employment dates authoritative for experience, retained stated experience only as validation evidence, and limited LLM experience to fallback use.
- Passed the already-extracted legacy resume, typed normalized resume, and deterministic experience from `CVService` into `MatchService`.
- Built one `CandidateAnalysisContext` per match analysis and reused the same `JobEvaluationContext` objects for pre-LLM and final scoring.
- Removed repeated resume parsing, per-vacancy candidate taxonomy/domain construction, and the final duplicate domain-profile extraction.
- Added normalized resume data additively to completed CV results and enriched match responses.
- Bumped `EXTRACTION_SCHEMA_VERSION` to `2.0.0` so older extraction/match cache entries cannot suppress the new structure.
- Added Phase 3 regressions for façade compatibility, normalized values/evidence, authoritative experience, context reuse, and supplied-resume reuse.
- Added `backend/docs/phase3-structured-cv-processing.md` and linked it from the README.
- Per repository instructions, did not run the application, tests, linting, builds, dependency restore, migrations, or external services.

## Files Created / Modified for Current Task
- Created schemas/services: `backend/app/schemas/normalized_resume.py`, `backend/app/services/document_conversion.py`,
  `backend/app/services/resume_text_normalizer.py`, `backend/app/services/resume_field_extractor.py`, `backend/app/services/resume_normalizer.py`,
  `backend/app/services/resume_quality.py`.
- Created tests/docs: `backend/tests/test_phase3_structured_processing.py`, `backend/docs/phase3-structured-cv-processing.md`.
- Modified integration: `backend/app/services/document_parser.py`, `backend/app/services/experience_calculator.py`,
  `backend/app/services/match_service.py`, `backend/app/services/cv_service.py`, `backend/app/services/vacancy_prefilter.py`,
  `backend/app/schemas/candidate_context.py`, `backend/app/schemas/analysis.py`, `backend/app/schemas/cv.py`, `backend/app/core/config.py`.
- Modified regression/docs: `backend/tests/test_experience_calculator.py`, `backend/tests/test_cv_idempotency.py`, `README.md`, `workstatus.md`.

## Pending Work
- Run the focused Phase 3 tests, broader backend suite, and Ruff only when explicitly authorized.
- Consider regional phone-number enrichment only when a trusted country/region source is available; current normalization intentionally avoids guessing country codes.
- Continue Phase 0 pending credential rotation and future access-policy enforcement.

## Important Decisions
- `app.services.document_parser` remains the stable compatibility import surface.
- Legacy response fields retain raw extracted values; typed normalized data is additive under `resume_json.normalized` and `normalized_resume`.
- Date-derived experience overrides conflicting or closely matching stated values; LLM experience cannot replace a dated calculation.
- Candidate and job contexts are created once per analysis and reused across confidence-gate and final scoring passes.
- `VacancyPreFilter.filter_vacancies` preserves dictionary output by default and returns reusable contexts only when explicitly requested.
- Ollama generation remains centralized in `OllamaLLMService`; no client, retry, timeout, or cache implementation was duplicated.

## Previous Task — Phase 2 Correct Identity and Caching
- Added canonical CV identity resolution that prioritizes supplied candidate/CV IDs and preserves normalized filename keys as compatibility aliases.
- Added collision checks before enqueue and again under the processing lock so unrelated candidates cannot silently overwrite a shared canonical key.
- Made legacy filename aliases resolve only when they identify one canonical result; ambiguous aliases no longer select an arbitrary candidate.
- Replaced filename-based Markdown reuse with `doc_cache_manager` entries keyed by document SHA-256, parser version, and schema version.
- Added indexed invalidation for versioned document extractions and routed candidate reprocessing through the centralized cache invalidator.
- Made `MatchService` compute SHA-256 for raw text when no document hash is supplied.
- Expanded final-match and optimized-LLM cache keys with document hash, canonical candidate identity, vacancy content version/IDs, prompt version,
  model, extraction version, and `MATCHING_VERSION`.
- Added full-vacancy-content version hashing so changed requirements isolate cached results even when vacancy IDs/titles remain unchanged.
- Isolated generic Ollama extraction fallbacks by prompt digest, prompt/model versions, and extraction version while retaining `OllamaLLMService` as the centralized client.
- Added cache-isolation, changed-content, identity-collision, legacy-alias, vacancy-version, and raw-text-hash regression tests.
- Documented the new identity, collision, compatibility, and cache contracts in `backend/docs/phase2-identity-and-caching.md`.
- Per repository instructions, did not run the application, tests, linting, builds, dependency restore, migrations, or external services.

## Files Created / Modified for Current Task
- Created: `backend/app/core/cv_identity.py`, `backend/docs/phase2-identity-and-caching.md`, `backend/tests/test_phase2_identity_cache.py`.
- Modified core/repositories: `backend/app/core/cache.py`, `backend/app/repositories/job.py`, `backend/app/repositories/llm_cache.py`,
  `backend/app/repositories/result.py`.
- Modified services/APIs: `backend/app/services/cv_service.py`, `backend/app/services/match_service.py`, `backend/app/services/llm_service.py`,
  `backend/app/services/upload_service.py`, `backend/app/api/cv.py`, `backend/app/api/analysis.py`, `backend/app/api/candidates.py`, `backend/app/api/batch.py`.
- Modified tests/docs: `backend/tests/test_cv_idempotency.py`, `backend/tests/test_audit_fixes.py`, `README.md`, `workstatus.md`.

## Pending Work
- Run the focused Phase 2 tests, broader backend suite, and Ruff only when explicitly authorized.
- Decide whether ambiguous legacy filename aliases should receive a dedicated canonical HTTP error contract in a later API-contract phase.
- Remove ignored legacy `{cv_key}.md` artifacts through a separate operational migration if disk cleanup is desired.
- Continue Phase 0 pending credential rotation and future access-policy enforcement.

## Important Decisions
- Supplied candidate/CV IDs define identity; filename-derived keys are canonical only when no IDs are supplied.
- The same supplied identity may receive changed content, while changed filename-only content returns HTTP 409 unless explicitly reprocessed.
- Legacy aliases are compatibility lookups, not ownership keys, and resolve only when unambiguous.
- Document extraction cache entries are content- and version-addressed; old result-directory Markdown files are never reused.
- Complete vacancy content is hashed separately from the existing lightweight repository staleness version to avoid altering current vacancy-cache behavior.
- Existing upload acknowledgements and polling response shapes remain unchanged.

## Previous Task — Phase 1 Secure Uploads
- Added `UploadService` as the single upload acceptance path for `/api/cv/upload` and `/api/match/upload`.
- Replaced unbounded upload reads with configurable bounded chunk reads and HTTP 413 responses at the configured size limit.
- Added cross-platform basename extraction, Unicode/character normalization, deterministic CV keys, and content-addressed server storage names.
- Added pre-persistence extension, declared-MIME, detected-signature, PDF structure/resource, and DOCX archive/structure/resource validation.
- Added atomic raw-file persistence, configurable age retention, success/failure cleanup policies, and result metadata linking a CV to its retained raw file.
- Changed candidate reprocessing to require and revalidate retained source bytes before cache/result invalidation; missing or invalid sources return HTTP 409 and preserve the existing result.
- Removed synthetic-PDF fallback reprocessing and legacy native `.doc`/`.txt` parser branches.
- Standardized supported uploads on PDF and DOCX; aligned settings, `.env.example`, Docker notes, README, tests, and Phase 1 documentation.
- Added focused tests for bounded reads, 413 behavior on both routes, filename safety, MIME/signature rejection, atomic storage, PDF/DOCX limits,
  cleanup policy, unsupported legacy formats, dual-route storage identity, and safe missing-source reprocessing.
- Per repository instructions, did not run the application, tests, linting, builds, dependency restore, migrations, or external services.

## Files Created / Modified for Current Task
- Created: `backend/app/services/upload_service.py`, `backend/docs/phase1-secure-uploads.md`, `backend/tests/test_upload_service.py`.
- Modified: `README.md`, `backend/.env.example`, `backend/Dockerfile`, `backend/app/core/config.py`, `backend/app/api/cv.py`,
  `backend/app/api/analysis.py`, `backend/app/api/candidates.py`, `backend/app/services/cv_service.py`, `backend/app/services/document_parser.py`.
- Modified tests: `backend/tests/test_audit_fixes.py`, `backend/tests/test_cv_extraction.py`, `backend/tests/test_docx_validation.py`,
  `backend/tests/test_dual_upload_key_alignment.py`, `backend/tests/test_frontend_polling_e2e.py`.
- Modified task record: `workstatus.md`.

## Pending Work
- Run the focused Phase 1 tests, broader backend suite, and Ruff only when explicitly authorized.
- Add isolated malware scanning/content disarm if uploads will be accepted from an untrusted public boundary.
- Configure matching request-body limits at the reverse proxy and schedule retention cleanup independently if uploads are infrequent.
- Continue Phase 0 pending credential rotation and future access-policy enforcement.

## Important Decisions
- PDF and DOCX remain supported; binary `.doc` and plain-text `.txt` uploads are rejected.
- Existing upload paths, HTTP 200 acknowledgement fields, polling contracts, and deterministic CV keys remain compatible.
- Raw uploads default to 30-day retention and are retained after both success and failure unless cleanup flags are enabled.
- Reprocessing never fabricates a document from extracted text; it uses only a retained, currently valid raw source.
- Raw storage uses `{cv_key}_{sha256}.{extension}` with atomic replacement and does not trust client paths.

## Previous Task — Phase 0 Characterization and Containment
- Captured 48 custom HTTP/WebSocket endpoints, current successful response shapes, polling states, compatibility aliases, and proposed access tiers in `backend/docs/phase0-api-contracts.md`.
- Added additive canonical error/job-state contracts and legacy adapters in `backend/app/schemas/contracts.py`; no existing endpoint behavior was changed.
- Added a complete public/recruiter/administrator endpoint policy in `backend/app/core/access_policy.py`; enforcement is intentionally deferred to the authorization phase.
- Added contract characterization tests covering route-policy completeness, compatibility aliases, legacy job-state normalization, polling adapters, and legacy error adaptation.
- Repaired stale idempotency, parser-timeout, batch-scan, and manual regression test references to match current parser methods, result statuses, outcome fields, and CV-key behavior.
- Privately audited tracked configuration/generated artifacts without printing credential values or CV contents.
- Removed `backend/.env`, `backend/final_output.json`, `backend/llm_cache.db`, and OS metadata from the Git index while retaining local copies.
- Added safe ignore rules and `backend/.env.example`.
- Did not run the application, tests, linting, builds, dependency restore, migrations, or external services.

## Files Created / Modified / Removed from Version Control for Phase 0
- Created: `backend/.env.example`, `backend/app/core/access_policy.py`, `backend/app/schemas/contracts.py`, `backend/docs/phase0-api-contracts.md`, `backend/docs/phase0-security-containment.md`, `backend/tests/test_phase0_contracts.py`.
- Modified: `.gitignore`, `backend/tests/test_cv_idempotency.py`, `backend/tests/test_batch_processing.py`, `backend/tests/regression/test_rrf_pipeline.py`, `workstatus.md`.
- Removed from Git tracking but retained locally: `backend/.env`, `backend/final_output.json`, `backend/llm_cache.db`, `backend/.DS_Store`, `backend/uploads/.DS_Store`.

## Pending Work
- Rotate the exposed `DB_PASSWORD` in the external database or secret manager, then update the untracked local/deployment secret. Repository access cannot perform this external rotation.
- Decide whether policy requires coordinated Git history rewriting after credential rotation.
- Run the Phase 0 characterization tests and Ruff checks only when explicitly authorized.
- Enforce the documented access tiers and integrate canonical errors/job states in later implementation phases.

## Important Decisions
- Phase 0 contracts are additive and do not alter current routes or response behavior.
- `NEW_CV`, `REPROCESSED`, and `CACHE_HIT` are processing outcomes; canonical terminal state is `COMPLETED`.
- Existing `/api/cv/*`, `/api/match/*`, `/api/candidates/*`, and `/api/v1/candidates/*` compatibility aliases remain supported.
- Public access is limited to `/` and `/health`; all CV, candidate, job, model, cache, configuration, and analytics operations require future recruiter or administrator authorization.
- The committed Redis URL contained no embedded credentials; the committed database password was non-empty.

## Previous Task — Backend Audit and Implementation Plan
- Completed a read-only audit of the backend architecture, API surface, upload paths, CV extraction, deterministic field extraction, scoring flow, Ollama generation, embeddings, caching, background processing, persistence, configuration, deployment files, and tests.
- Produced a prioritized implementation plan only; no backend functionality was implemented and no build, test, lint, restore, publish, or migration command was run.
- Identified critical risks around unsafe raw-upload paths, validation after persistence, unbounded upload buffering, unauthenticated administrative/PII endpoints, tracked environment/data artifacts, cache identity collisions, stale Markdown reuse, non-durable web-process background tasks, and deterministic experience not reaching scoring.
- Identified medium/low risks covering duplicated extraction/context work, inconsistent Ollama clients/timeouts/retries, per-CV model unloads, parser timeout cancellation, DOCX/PDF resource limits, API/error contract drift, deployment configuration drift, stale tests, and outdated documentation.

## Files Created / Modified / Deleted for Current Task
- Modified: `workstatus.md` only, as required by repository instructions.
- Backend code changes: none.

## Pending Work
- Implement the approved plan in prioritized phases, beginning with contract characterization and security containment.
- Run tests and linting only when implementation is explicitly authorized.

## Important Decisions
- Preserve existing API paths and response contracts through adapters while consolidating internal upload and analysis flows.
- Reuse `app.core.config.settings`, RQ/Redis, existing repositories/cache managers, `OllamaLLMService`, and `EmbeddingService`.
- Make deterministic extraction authoritative for normalized candidate data and scoring; treat LLM output as enrichment/fallback.
- Key extraction and match caches by content hash plus relevant parser/schema/model/prompt/matching versions.
- Validate and sanitize uploads before any disk write or background enqueue.

## Previous Task — Experience Calculation
- **Centralized Experience Calculation**:
  - Implemented `ExperienceCalculator` in [backend/app/services/experience_calculator.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/experience_calculator.py) to dynamically calculate experience from chronological work history.
  - Added interval merging logic to handle overlapping jobs and avoid double counting.
  - Added logic to automatically resolve "Present" or "Current" roles to `datetime.now()` for real-time month-level precision.
  - Implemented explicit text validation to prevent discrepancies between stated experience and computed dates.
  - Integrated `ExperienceCalculator` into `process_cv` within [backend/app/services/cv_service.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/cv_service.py).
  - Modified `CandidateAnalysisContext` in [backend/app/schemas/candidate_context.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/schemas/candidate_context.py) to prioritize the deterministic `experience_years` over LLM outputs.
  - Wrote and passed comprehensive unit tests in [backend/tests/test_experience_calculator.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/tests/test_experience_calculator.py).
  - Validated candidate `cv_Utkarsh_Patil_07012026` successfully, verifying dynamic experience updates.

## Files Created / Modified / Deleted
- Modified: [backend/app/services/cv_service.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/cv_service.py), [backend/app/schemas/candidate_context.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/schemas/candidate_context.py)
- Created: [backend/app/services/experience_calculator.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/experience_calculator.py), [backend/tests/test_experience_calculator.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/tests/test_experience_calculator.py)
- Artifacts: `implementation_plan.md`, `task.md`, `walkthrough.md`

## Pending Work
- None.
