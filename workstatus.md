# Work Status

## Last Updated
2026-08-03T12:21:04+05:30

## Current Task — Phase 2 Correct Identity and Caching
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
