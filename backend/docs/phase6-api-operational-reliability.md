# Phase 6 — API and Operational Reliability

## Request context and error contract

Every HTTP request receives `X-Request-ID` and `X-Correlation-ID` response headers. A caller may supply either header when its value contains only letters, numbers,
periods, underscores, colons, or hyphens and is no longer than 128 characters. Unsafe values are replaced with a generated identifier.

HTTP exceptions, validation failures, authorization failures, rate limits, oversized JSON bodies, and unexpected errors use the same envelope. The legacy `detail`
field remains additive during compatibility migration:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "request_id": "4b6d...",
    "correlation_id": "4b6d...",
    "retryable": false,
    "details": {
      "violations": []
    }
  },
  "detail": "Request validation failed."
}
```

Validation details contain field location, validation type, and a safe message; submitted CV text and feedback values are never echoed. Unexpected exception traces
are logged server-side with both identifiers and are returned only as `INTERNAL_ERROR` with a generic message.

Failed processing records no longer persist tracebacks. Both polling aliases force the legacy `error_details` field to `null`, including when an older stored result
still contains traceback text.

## Authentication and authorization

The Phase 0 endpoint policy is now enforced by `AccessControlMiddleware`. Configure JSON arrays of independent secrets:

```dotenv
AUTH_ENABLED=true
RECRUITER_API_KEYS=["replace-with-a-generated-recruiter-secret"]
ADMINISTRATOR_API_KEYS=["replace-with-a-generated-administrator-secret"]
```

Clients authenticate with `Authorization: Bearer <key>` or `X-API-Key: <key>`. Administrator credentials inherit recruiter access. API keys are compared in constant
time and are never written to logs. Rate limits are keyed by client address so invalid or rotating credentials cannot bypass the containment limit.

Local development can set `AUTH_ENABLED=false`. Production and staging always require authentication regardless of that toggle. When production has no keys,
public `/` and `/health` remain available while protected endpoints fail closed with HTTP 503. PII, CV upload/text/polling, candidate search/details, batch matching,
and HR review require recruiter access. Reprocessing, training data, LLM health, configuration, cache invalidation/analytics, warmup, vector synchronization/status,
performance metrics, and administrative taxonomy mutation require administrator access according to `access_policy.py`.

The WebSocket progress endpoint requires an authenticated handshake when production authorization is enabled. Browser deployments should terminate authentication at
a trusted same-origin gateway or use a session-capable proxy; API keys should not be placed in WebSocket query strings.

## Input and rate limits

| Setting | Default | Purpose |
| --- | ---: | --- |
| `MAX_JSON_REQUEST_SIZE_BYTES` | `1048576` | Reject declared JSON bodies over 1 MiB before parsing |
| `MAX_CV_TEXT_LENGTH_CHARS` | `500000` | Maximum raw CV text field length |
| `MAX_HR_FEEDBACK_LENGTH_CHARS` | `10000` | Maximum HR feedback length |
| `RATE_LIMIT_ENABLED` | `true` | Enable the application-boundary limiter |
| `RATE_LIMIT_REQUESTS` | `300` local, `120` Compose | Requests allowed per identity/window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding-window duration |
| `RATE_LIMIT_MAX_BUCKETS` | `10000` | Bound per-process limiter memory |

Rate-limit responses use HTTP 429, `RATE_LIMITED`, and `Retry-After`. Successful protected responses expose limit, remaining, and reset headers. The in-process limiter
uses the socket peer address and intentionally does not trust spoofable forwarded headers. Deployments behind a proxy or with multiple API replicas should enforce
the authoritative per-client/shared limit at the ingress/API gateway; the application limit then remains coarse containment.

## CORS

Wildcard origins are discarded. The default trusted origin is `http://localhost:8081`; deployments must set an explicit JSON array in `ALLOWED_ORIGINS`.
Credentials are disabled by default, methods and headers are enumerated, and only request/correlation/rate-limit headers are exposed.

## Lifespan and migrations

Importing `app.main` no longer calls `init_db` or the migration runner. FastAPI lifespan owns local schema initialization, Redis/Ollama checks, cache warmup, and Ollama
transport cleanup.

`INITIALIZE_DATABASE_ON_STARTUP` and `AUTO_MIGRATE` are ignored in production/staging. Production migrations use the explicit migration runner. For the Compose
PostgreSQL service:

```bash
docker compose --profile tools run --rm migrate-postgres
```

PostgreSQL migration `007_create_vector_embeddings.sql` creates the pgvector extension and embedding tables that were formerly supplied by startup `create_all()`.
MSSQL migration `007_create_system_config.sql` similarly makes the matching configuration table explicit.

Local development may retain `INITIALIZE_DATABASE_ON_STARTUP=true`; automatic local migrations remain opt-in and default to false.

## Docker alignment

- API, worker, and migration services share one environment mapping.
- Compose now supplies `POSTGRES_APP_URL` and `MSSQL_READ_ONLY_URL`, matching the application setting, instead of legacy variables.
- The queue name is shared between worker command and API configuration.
- Redis and PostgreSQL readiness gate API/worker startup; API liveness plus worker, Redis, and PostgreSQL health checks have restart behavior.
- The Python base image is pinned to Debian Bookworm. The image includes Microsoft ODBC Driver 18 for the configured MSSQL dialect plus the PDF/OCR runtime libraries.
- Schema migration is an explicit tools-profile service and never runs as part of normal API or worker startup.

## Compatibility

Existing successful response bodies and route aliases are unchanged. Error responses add the canonical envelope and retain top-level `detail`. Failed polling retains
the legacy `error_details` field as `null`. Authentication is disabled by default only for local development; production enforcement is intentional.
