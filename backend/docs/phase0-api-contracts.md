# Phase 0 API Characterization and Contracts

This document captures the current FastAPI surface statically from route decorators and Pydantic models.
The application was not started and OpenAPI was not generated at runtime because repository instructions prohibit running the project unless explicitly requested.

## Access tiers

- `public`: unauthenticated liveness and service-discovery endpoints only.
- `recruiter`: authenticated recruiter/HR workflows and candidate/job data.
- `administrator`: configuration, cache, model, vector, training-data, taxonomy mutation, and reprocessing operations.

Phase 0 defines these tiers in `app.core.access_policy`; it does not yet enforce authentication.

## Endpoint inventory

All API routers are mounted below `/api`. Candidate routes are also mounted below `/api/v1` as compatibility aliases.

| Method | Path | Successful response | Access |
|---|---|---|---|
| GET | `/` | `{message, docs, health}` | public |
| GET | `/health` | `{status, version, database, pg_database, ollama_llm}` | public |
| GET | `/api/match/health` | Disabled, online, or offline Ollama status object | administrator |
| POST | `/api/match/analyze` | `EnrichedCandidateAnalysis` | recruiter |
| POST | `/api/match/upload` | `CVProcessingResponse` | recruiter |
| GET | `/api/match/status/{cv_key}` | `CVProcessingResponse`, `EnrichedCandidateAnalysis`, or legacy result object | recruiter |
| POST | `/api/match/reanalyze/{scan_id}` | `EnrichedCandidateAnalysis` | recruiter |
| POST | `/api/match/hr-review` | `{status, message}` | recruiter |
| GET | `/api/match/training-data` | `{count, examples}` | administrator |
| POST | `/api/cv/upload` | `CVProcessingResponse` | recruiter |
| POST | `/api/cv/match` | `EnrichedCandidateAnalysis` or `CandidateMatchAnalysis` | recruiter |
| GET | `/api/cv/status/{cv_key}` | `CVUploadResponse` or `CVProcessingResponse` | recruiter |
| GET | `/api/jobs` | `list[JobOpening]` | recruiter |
| POST | `/api/jobs/cache/invalidate` | `{message}` | administrator |
| GET | `/api/jobs/{job_id}` | `JobOpening` | recruiter |
| GET | `/api/master-data/job-profiles` | `list[object]` | recruiter |
| GET | `/api/master-data/departments` | `list[object]` | recruiter |
| GET | `/api/master-data/companies` | `list[object]` | recruiter |
| GET | `/api/master-data/skills` | `list[object]` | recruiter |
| POST | `/api/master-data/warm` | `{message, counts}` | administrator |
| POST | `/api/batch/match-candidates` | `{message, matches}` | recruiter |
| WEBSOCKET | `/api/batch/ws/progress` | Redis-published progress JSON as text frames | recruiter |
| GET | `/api/config/match` | `MatchEngineConfigResponse` | administrator |
| PUT | `/api/config/match` | `MatchEngineConfigResponse` | administrator |
| POST | `/api/candidates/search` | `CandidateSearchResponse` | recruiter |
| GET | `/api/candidates` | `list[CandidateSearchResultItem]` serialized as objects | recruiter |
| GET | `/api/candidates/{candidate_id}` | Stored candidate result object | recruiter |
| POST | `/api/candidates/{candidate_id}/reprocess` | Processing status object | administrator |
| POST | `/api/v1/candidates/search` | Alias of `/api/candidates/search` | recruiter |
| GET | `/api/v1/candidates` | Alias of `/api/candidates` | recruiter |
| GET | `/api/v1/candidates/{candidate_id}` | Alias of `/api/candidates/{candidate_id}` | recruiter |
| POST | `/api/v1/candidates/{candidate_id}/reprocess` | Alias of `/api/candidates/{candidate_id}/reprocess` | administrator |
| GET | `/api/analytics/cache` | `{global_metrics, per_namespace, system_stats}` | administrator |
| GET | `/api/vector-db/status` | Vector migration/service status object | administrator |
| POST | `/api/vector-db/sync` | `{message, status}` | administrator |
| GET | `/api/domain-knowledge/categories` | `list[str]` | recruiter |
| POST | `/api/domain-knowledge/equivalents` | `DomainEquivalentResponse` | recruiter |
| POST | `/api/domain-knowledge/designations` | `{status, message, designation_name, family_name}` | administrator |
| POST | `/api/domain-knowledge/resolve-role` | `DynamicTaxonomyResult` | recruiter |
| GET | `/api/talent-graph/candidate/{candidate_id}` | Candidate graph object | recruiter |
| GET | `/api/talent-graph/vacancy/{vacancy_id}` | Vacancy graph object | recruiter |
| GET | `/api/talent-graph/skill/{skill_name}` | Skill graph object | recruiter |
| GET | `/api/talent-graph/analytics` | Recruitment graph analytics object | recruiter |
| GET | `/api/recommendations/candidate/{candidate_id}` | Candidate recommendation object | recruiter |
| GET | `/api/recommendations/vacancy/{vacancy_id}` | Vacancy recommendation object | recruiter |
| GET | `/api/recommendations/talent-pools` | Talent-pool object | recruiter |
| GET | `/api/performance/metrics` | Performance metrics object | administrator |
| POST | `/api/performance/cache/invalidate` | `CacheInvalidateResponse` | administrator |

## Current successful response shapes

### Upload acknowledgement

Both upload routes currently return HTTP 200 with:

```json
{
  "message": "string",
  "cv_key": "string",
  "status": "processing",
  "progress": 10,
  "stage": null,
  "failed_step": null,
  "error_details": null
}
```

### Completed CV result

`GET /api/cv/status/{cv_key}` returns `CVUploadResponse` after completion. Stable top-level compatibility fields are:

```text
id, scan_id, parsed_at, filename, content_type, characters, page_count,
is_scanned, ocr_applied, text, markdown, match_analysis, result_file_path,
candidate_id, cv_id, cv_hash, parser_version, schema_version, created_at,
updated_at, status, resume_json, quality_metrics, candidate identity fields
```

### Match result

`EnrichedCandidateAnalysis` contains:

```text
status, progress, stage, is_complete, full_name, candidate_name,
primary_department, recommended_department, professional_domain, strengths,
suitable_job_roles, has_genuine_match, active_vacancy_summary,
ai_career_summary, best_match, suitable_openings, rejection_policy_note,
llm_skipped
```

### Candidate search

`CandidateSearchResponse` contains `total_found`, `search_mode`, `query`, and `candidates`.
Candidate items include identifying/contact data, confidence fields, extraction metadata, department, similarity, and best-match summary.

## Polling contract

### Canonical states

| State | Meaning | Terminal | Expected progress |
|---|---|---:|---:|
| `QUEUED` | Accepted and durably queued | No | 0-10 |
| `PROCESSING` | A worker is actively processing the CV | No | 1-99 |
| `RETRYING` | A retryable failure occurred and another attempt is scheduled | No | Last known value |
| `COMPLETED` | Processing finished and the result is available | Yes | 100 |
| `FAILED` | Processing ended unsuccessfully | Yes | 100 |
| `UNKNOWN` | Compatibility input could not be mapped | No | As supplied |

`NEW_CV`, `REPROCESSED`, and `CACHE_HIT` are outcomes, not canonical job states.

### Existing state aliases

| Existing value | Canonical state |
|---|---|
| `processing`, `PROCESSING`, `IN_PROGRESS` | `PROCESSING` |
| `NEW_CV`, `REPROCESSED`, `CACHE_HIT`, `COMPLETED` | `COMPLETED` |
| `CV_CHANGED`, `SCHEMA_CHANGED` | `PROCESSING` |
| `FAILED`, `ERROR` | `FAILED` |

The canonical `JobStateResponse` uses `job_id`, `state`, `progress`, `stage`, `message`, `outcome`, and a sanitized error.
Its legacy adapter preserves `cv_key`, `status`, `progress`, `stage`, `failed_step`, and `error_details` without returning a traceback.

## Error contract

The current API primarily returns FastAPI's legacy shape:

```json
{"detail": "Human-readable message"}
```

Request validation currently uses FastAPI's standard 422 `detail` list. The target canonical envelope is additive and versionable:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "request_id": "optional-correlation-id",
    "retryable": false,
    "details": {}
  }
}
```

Canonical error codes are `VALIDATION_ERROR`, `NOT_FOUND`, `CONFLICT`, `UNAUTHORIZED`, `FORBIDDEN`, `PAYLOAD_TOO_LARGE`, `UNSUPPORTED_FILE`,
`DEPENDENCY_UNAVAILABLE`, `PROCESSING_FAILED`, and `INTERNAL_ERROR`.

Existing endpoints continue returning `detail` until centralized exception handling is introduced. `ErrorResponse.to_legacy_detail()` defines the compatibility adapter.

## Compatibility aliases

- `/api/cv/upload` and `/api/match/upload` share the upload acknowledgement and CV-key contract.
- `/api/cv/status/{cv_key}` and `/api/match/status/{cv_key}` share lifecycle semantics but intentionally retain their current distinct completed-result shapes.
- `/api/cv/match` and `/api/match/analyze` are raw-text matching aliases.
- `/api/candidates/*` and `/api/v1/candidates/*` are identical router mounts.
- Result lookup accepts `cv_`, `CV_`, and unprefixed stem variations.
- Stored compatibility pairs include `id`/`scan_id`, `parsed_at`/`scanned_at`, `text`/`markdown`, and `full_name`/`candidate_name`.

## Phase 0 invariants

1. No existing route is removed or renamed.
2. Existing success response fields remain available.
3. Existing `detail` errors remain available until a versioned migration is implemented.
4. Legacy polling values normalize to canonical states without changing existing endpoints.
5. Every custom route must have an access-tier policy before authorization enforcement is added.
