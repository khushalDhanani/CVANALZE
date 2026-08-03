# Work Status

## Last Updated
2026-08-03T11:37:33+05:30

## Current Task — Phase 0 Characterization and Containment
- Captured 48 custom HTTP/WebSocket endpoints, current successful response shapes, polling states, compatibility aliases, and proposed access tiers in `backend/docs/phase0-api-contracts.md`.
- Added additive canonical error/job-state contracts and legacy adapters in `backend/app/schemas/contracts.py`; no existing endpoint behavior was changed.
- Added a complete public/recruiter/administrator endpoint policy in `backend/app/core/access_policy.py`; enforcement is intentionally deferred to the authorization phase.
- Added contract characterization tests covering route-policy completeness, compatibility aliases, legacy job-state normalization, polling adapters, and legacy error adaptation.
- Repaired stale idempotency, parser-timeout, batch-scan, and manual regression test references to match current parser methods, result statuses, outcome fields, and CV-key behavior.
- Privately audited tracked configuration/generated artifacts without printing credential values or CV contents.
- Removed `backend/.env`, `backend/final_output.json`, `backend/llm_cache.db`, and OS metadata from the Git index while retaining local copies.
- Added safe ignore rules and `backend/.env.example`.
- Did not run the application, tests, linting, builds, dependency restore, migrations, or external services.

## Files Created / Modified / Removed from Version Control for Current Task
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
