# Phase 4 — Reliable Background Processing

## Architecture

Both `POST /api/cv/upload` and `POST /api/match/upload` now use `ProcessingQueueService`. The API validates and atomically stores the raw PDF/DOCX,
checks canonical identity ownership, persists a processing-job record, and then enqueues only the job ID to Redis/RQ. The RQ worker reloads and revalidates the
retained source before invoking the existing `process_cv_file` pipeline.

`POST /api/candidates/{candidate_id}/reprocess` uses the same queue path with `force_reprocess=true`. It continues to verify source availability and document
validity before invalidating the prior result or any cache entry.

## Job identity and idempotency

The canonical processing-job ID is a SHA-256 digest over:

- canonical CV key;
- source content SHA-256;
- extraction parser version; and
- extraction schema version.

Repeated submissions of the same active or completed content identity reuse the existing job. Changed source content or extraction versions create an isolated job.
Submission and execution use Redis distributed locks; an in-process lock is retained as a local-development safety net. The existing canonical CV lock inside
`process_cv_file` remains the final overwrite guard.

Workers compare the retained source SHA-256 with the persisted job identity before processing. The RQ payload never contains raw CV bytes.

## Persisted state contract

Jobs are stored through the existing cache-manager tiers under a dedicated `processing_job` namespace. For this namespace Redis and the shared file provider are
both written so a worker can recover a record even if the API started while Redis was unavailable.

Canonical transitions are:

```text
QUEUED -> PROCESSING -> COMPLETED
                     -> RETRYING -> PROCESSING
                     -> FAILED
```

Each record includes attempts, maximum attempts, execution mode, RQ job ID, timestamps, progress, stage, and a canonical error. A record is persisted as `QUEUED`
before `Queue.enqueue` is called. Retry state is persisted before the worker rethrows an exception to RQ.

Legacy clients continue to receive lowercase `status="processing"` for `QUEUED`, `PROCESSING`, and `RETRYING`. Responses add `job_id`, `job_state`,
`execution_mode`, and `retry_count` without removing existing fields.

## Redis outage behavior

The in-process FastAPI background runner is an explicit development fallback, not the production default. It is allowed only when both conditions are true:

- `APP_ENVIRONMENT` is `dev`, `development`, `local`, or `test`; and
- `RQ_DEVELOPMENT_FALLBACK_ENABLED=true`.

The fallback uses the same persisted job record, source validation, state transitions, and retry count. Production Docker services set
`APP_ENVIRONMENT=production` and disable it. If Redis/RQ is unavailable in that configuration, the job becomes `FAILED` at the enqueue stage and the upload
endpoint returns HTTP 503.

## Polling compatibility and not found

Unknown IDs now return HTTP 404 by default from both polling aliases. A deployment can temporarily retain the former synthetic processing response by setting
`JOB_NOT_FOUND_COMPATIBILITY_UNTIL` to a future ISO-8601 timestamp. Once that deadline expires—or when it is unset—the real not-found contract applies.

Persisted job state takes precedence over a transient failed result while RQ is waiting to retry. Completed result response shapes remain compatible.

## Docker Compose worker

Docker Compose includes a `worker` service consuming the `cv-processing` queue. It shares the uploads volume with the API, waits for healthy Redis, restarts unless
stopped, and exposes an RQ/Redis health check. Redis now has its own health check.

## Configuration

| Setting | Default | Purpose |
| --- | ---: | --- |
| `RQ_QUEUE_NAME` | `cv-processing` | API and worker queue name |
| `RQ_JOB_TIMEOUT_SECONDS` | `900` | RQ execution timeout |
| `RQ_RESULT_TTL_SECONDS` | `604800` | RQ result retention |
| `RQ_MAX_RETRIES` | `2` | Retries after the first attempt |
| `RQ_RETRY_INTERVAL_SECONDS` | `30` | Delay between retries |
| `PROCESSING_JOB_TTL_SECONDS` | `604800` | Redis processing-record retention |
| `PROCESSING_JOB_LOCK_TIMEOUT_SECONDS` | `1200` | Distributed execution-lock lease |
| `RQ_DEVELOPMENT_FALLBACK_ENABLED` | `true` | Allows fallback only in a development environment |
| `JOB_NOT_FOUND_COMPATIBILITY_UNTIL` | unset | Optional legacy unknown-job deadline |

## Operational notes

- API and worker must share the raw uploads/results volume.
- The lock timeout must exceed the maximum expected pipeline duration.
- The RQ worker uses the existing centralized Ollama, extraction, matching, and cache services; it does not create another model client.
- Raw-file success/failure retention remains governed by the Phase 1 upload policy.
- RQ and processing-record TTLs should exceed the longest supported polling window.
