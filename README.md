# CV Analyzer

CV Analyzer is a FastAPI backend for securely ingesting resumes, extracting normalized candidate data, matching candidates to vacancies, and exposing recruiter and
administrator workflows. PDF and DOCX uploads are processed asynchronously through Redis/RQ, while deterministic scoring can be enriched by a local Ollama service.

## Supported CV formats

| Format | Upload support | Notes |
| --- | --- | --- |
| PDF | Supported | Signature, MIME type, structure, encryption, page, image, object, area, and embedded-file limits are checked before persistence. |
| DOCX | Supported | ZIP structure, encryption, paths, links, macros, entry count, expanded size, and compression ratio are checked before persistence. |
| DOC | Not supported | Binary Word conversion is intentionally excluded because the deployed image has no isolated legacy-conversion sandbox. |
| TXT | Not supported | Plain text has no dependable file signature and is accepted only by the bounded raw-text analysis APIs, not as an uploaded file. |

Both upload aliases read files in bounded chunks, reject over-limit files with HTTP 413, and persist accepted content atomically under a server-generated name. The
default compressed upload limit is 15 MiB. See [Phase 1](backend/docs/phase1-secure-uploads.md) for the complete acceptance and retention policy.

## Architecture

```text
Client
  -> request/correlation context -> trusted CORS -> rate limit -> API-key access policy
  -> FastAPI routes and Pydantic schemas
       -> UploadService -> atomic shared uploads storage
       -> ProcessingQueueService -> persisted job record -> Redis/RQ worker
       -> document_parser compatibility facade
            -> conversion -> text normalization -> field extraction -> quality metrics
       -> CandidateAnalysisContext + reusable JobEvaluationContext objects
       -> deterministic scoring -> optional OllamaLLMService enrichment
       -> versioned caches and result repositories

External/runtime services
  -> Redis: RQ, distributed locks, processing records, and cache tier
  -> PostgreSQL/pgvector: embeddings and vector-backed services
  -> MSSQL: configured recruiting, taxonomy, and system data
  -> Ollama: pooled generation and embedding transport
  -> shared uploads volume: retained raw files, results, file cache, and training data
```

Key boundaries are intentionally centralized:

- `backend/app/api/` owns HTTP and WebSocket adapters.
- `backend/app/core/` owns configuration, identity, caching, access control, request context, errors, rate limiting, and lifespan behavior.
- `backend/app/schemas/` owns legacy-compatible API models and typed normalized resume/job contexts.
- `backend/app/services/` owns upload, extraction, matching, scoring, queueing, Ollama, embedding, search, recommendations, and synchronization workflows.
- `backend/app/repositories/` owns jobs, results, processing records, cache data, and training data.
- `backend/scripts/migrations/` contains explicit PostgreSQL and MSSQL migrations; production startup never mutates schemas.

## API access model

`GET /` and `GET /health` are public. Candidate PII, uploads, status polling, raw-text analysis, jobs, search, matching, recommendations, and HR review require recruiter
access. Configuration, reprocessing, cache administration, warmup, synchronization, training data, model health, taxonomy mutation, and performance metrics require
administrator access. Uncharacterized `/api/*` routes fail closed as administrator-only.

Authenticate with either header:

```http
Authorization: Bearer <api-key>
X-API-Key: <api-key>
```

Administrator keys inherit recruiter permissions. `AUTH_ENABLED=false` is available for local development, but production and staging always require authentication.
Protected endpoints return HTTP 503 when authentication is required and no keys are configured.

The characterized endpoint inventory and successful response shapes are in [Phase 0 API contracts](backend/docs/phase0-api-contracts.md). The enforced policy is
documented in [Phase 6](backend/docs/phase6-api-operational-reliability.md).

## Upload and background-job flow

1. `POST /api/cv/upload` or `POST /api/match/upload` validates the entire document before writing or enqueueing it.
2. The service resolves a canonical CV identity. Supplied candidate/CV IDs take precedence; filename keys remain compatibility aliases.
3. The accepted file is atomically stored, and a processing record is persisted before enqueueing.
4. Redis/RQ receives only the job ID. The worker reloads, revalidates, and hash-checks the retained source.
5. Distributed locks and content/version identity make duplicate work idempotent.
6. Clients poll either status alias until a terminal state is returned.

Upload acknowledgements retain the legacy fields and add canonical job metadata:

```json
{
  "message": "CV processing is queued.",
  "cv_key": "cv_candidate_123_document_456",
  "status": "processing",
  "progress": 10,
  "stage": "queued",
  "job_id": "content-and-version-addressed-id",
  "job_state": "QUEUED",
  "execution_mode": "RQ",
  "retry_count": 0,
  "failed_step": null,
  "error_details": null
}
```

### Job states

```text
QUEUED -> PROCESSING -> COMPLETED
                     -> RETRYING -> PROCESSING
                     -> FAILED
```

| State | Meaning | Terminal |
| --- | --- | ---: |
| `QUEUED` | The record is persisted and waiting for a worker. | No |
| `PROCESSING` | A worker owns the job and is processing the retained source. | No |
| `RETRYING` | A retryable failure occurred and another attempt is scheduled. | No |
| `COMPLETED` | The result is available. | Yes |
| `FAILED` | Processing stopped after a non-retryable error or exhausted attempts. | Yes |
| `UNKNOWN` | A legacy value or temporary unknown-job adapter could not map to a persisted state. | No |

`NEW_CV`, `REPROCESSED`, and `CACHE_HIT` are outcomes, not states. Legacy clients continue to see `status="processing"` for queued, active, and retrying jobs.
Unknown job IDs return HTTP 404 unless a future `JOB_NOT_FOUND_COMPATIBILITY_UNTIL` temporarily enables the former synthetic processing response.

## Error contract

All centralized HTTP errors use one stable envelope and retain top-level `detail` for existing clients:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed.",
    "request_id": "6c925c5b...",
    "correlation_id": "6c925c5b...",
    "retryable": false,
    "details": {
      "violations": []
    }
  },
  "detail": "Request validation failed."
}
```

The canonical codes are `VALIDATION_ERROR`, `NOT_FOUND`, `CONFLICT`, `UNAUTHORIZED`, `FORBIDDEN`, `PAYLOAD_TOO_LARGE`, `UNSUPPORTED_FILE`,
`DEPENDENCY_UNAVAILABLE`, `PROCESSING_FAILED`, `RATE_LIMITED`, and `INTERNAL_ERROR`. Common status mappings are 400/422 validation, 401 unauthenticated,
403 forbidden, 404 missing, 409 conflict, 413 oversized, 415 unsupported media, 429 rate limited, 500 internal, and 503 dependency unavailable.
Secure-upload policy violations preserve HTTP 400 for compatibility, while oversized uploads use 413; 415 remains available for unsupported HTTP media contracts.

Every HTTP response includes `X-Request-ID` and `X-Correlation-ID`; safe caller-provided values are preserved. Stack traces stay in server logs. Polling responses retain
`error_details` only as a compatibility field and always return it as `null`.

## Configuration

For local development, copy `backend/.env.example` to the ignored `backend/.env`. Pydantic accepts booleans and numbers in normal environment syntax; list settings
such as origins and API keys must be JSON arrays. Never commit real credentials.

### Runtime, access, and request controls

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENVIRONMENT` | `development` | Enables production/staging containment when set to `production`, `prod`, or `staging`. |
| `AUTH_ENABLED` | `false` | Enables API-key enforcement locally; production/staging always enforce it. |
| `RECRUITER_API_KEYS` | `[]` | JSON array of recruiter secrets. |
| `ADMINISTRATOR_API_KEYS` | `[]` | JSON array of administrator secrets. |
| `ALLOWED_ORIGINS` | `["http://localhost:8081"]` | Explicit trusted CORS origins; wildcard entries are ignored. |
| `CORS_ALLOW_CREDENTIALS` | `false` | Enables credentialed cross-origin requests only for trusted origins. |
| `RATE_LIMIT_ENABLED` | `true` | Enables the per-process application containment limit. |
| `RATE_LIMIT_REQUESTS` | `300` local, `120` Compose | Requests allowed per socket-peer bucket and window. |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding-window duration. |
| `RATE_LIMIT_MAX_BUCKETS` | `10000` | Maximum in-process limiter buckets. |
| `MAX_JSON_REQUEST_SIZE_BYTES` | `1048576` | Maximum declared JSON request size. |
| `MAX_CV_TEXT_LENGTH_CHARS` | `500000` | Maximum raw CV text field length. |
| `MAX_HR_FEEDBACK_LENGTH_CHARS` | `10000` | Maximum HR review feedback length. |
| `INITIALIZE_DATABASE_ON_STARTUP` | `true` local | Allows local schema initialization; ignored in production/staging. |
| `STARTUP_CACHE_WARMUP_ENABLED` | `true` | Starts best-effort cache warmup during lifespan startup. |
| `AUTO_MIGRATE` | `false` | Opt-in local automatic migration; ignored in production/staging. |

### Databases, Redis, and RQ

| Variable | Default | Purpose |
| --- | --- | --- |
| `PG_DB_URL` | local PostgreSQL URL | PostgreSQL/pgvector connection string. |
| `DB_SERVER`, `DB_PORT`, `DB_NAME` | local/empty | Optional MSSQL location and database. Empty `DB_NAME` disables the MSSQL engine. |
| `DB_USER`, `DB_PASSWORD` | empty | MSSQL credentials. |
| `DB_ENCRYPT`, `DB_TRUST_CERT` | `true`; template trust is `false` | ODBC encryption and certificate trust policy. |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection for RQ, locks, processing records, and cache. |
| `RQ_QUEUE_NAME` | `cv-processing` | Queue consumed by the API and worker. |
| `RQ_JOB_TIMEOUT_SECONDS` | `900` | Worker execution timeout. |
| `RQ_RESULT_TTL_SECONDS` | `604800` | RQ result retention in seconds. |
| `RQ_MAX_RETRIES` | `2` | Retries after the first attempt. |
| `RQ_RETRY_INTERVAL_SECONDS` | `30` | Delay between retries. |
| `RQ_DEVELOPMENT_FALLBACK_ENABLED` | `true` | Allows the in-process fallback only in local/development/test environments. |
| `PROCESSING_JOB_TTL_SECONDS` | `604800` | Redis processing-record retention. |
| `PROCESSING_JOB_LOCK_TIMEOUT_SECONDS` | `1200` | Distributed execution-lock lease. |
| `JOB_NOT_FOUND_COMPATIBILITY_UNTIL` | unset | Optional ISO-8601 deadline for the legacy unknown-job response. |

### Upload policy

| Variable | Default | Purpose |
| --- | --- | --- |
| `ALLOWED_EXTENSIONS` | `["pdf","docx"]` | Upload extension allowlist. The documented and tested support contract is PDF/DOCX only. |
| `MAX_FILE_SIZE_BYTES` | `15728640` | Maximum compressed upload size. |
| `UPLOAD_READ_CHUNK_SIZE_BYTES` | `1048576` | Maximum upload read size per iteration. |
| `UPLOAD_FILENAME_MAX_CHARS` | `120` | Maximum normalized display filename length. |
| `MAX_DOCX_EXPANDED_SIZE_BYTES` | `78643200` | Maximum combined uncompressed DOCX size. |
| `MAX_DOCX_ENTRIES` | `2000` | Maximum DOCX archive entries. |
| `MAX_DOCX_COMPRESSION_RATIO` | `200` | Maximum per-entry and aggregate expansion ratio. |
| `MAX_PDF_PAGES` | `100` | Maximum PDF pages. |
| `MAX_PDF_XREF_OBJECTS` | `10000` | Maximum PDF cross-reference objects. |
| `MAX_PDF_IMAGES` | `1000` | Maximum images across all PDF pages. |
| `MAX_PDF_TOTAL_PAGE_AREA_POINTS` | `500000000` | Maximum aggregate PDF page area. |
| `MAX_PDF_EMBEDDED_FILES` | `0` | Maximum PDF embedded attachments. |
| `RAW_UPLOAD_RETENTION_DAYS` | `30` | Opportunistic raw-file age retention; negative disables age cleanup. |
| `RAW_UPLOAD_DELETE_ON_SUCCESS` | `false` | Deletes accepted source files after success when enabled. |
| `RAW_UPLOAD_DELETE_ON_FAILURE` | `false` | Deletes accepted source files after terminal failure when enabled. |

### Ollama and embeddings

| Variable | Default | Purpose |
| --- | --- | --- |
| `LLM_ENABLED` | `true` | Enables semantic generation; deterministic scoring remains available when disabled. |
| `EMBEDDING_ENABLED` | `true` | Enables embedding-backed retrieval and related features. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint; Compose defaults to `host.docker.internal`. |
| `OLLAMA_MODEL` | `qwen3:4b` | Generation model. |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model. |
| `OLLAMA_REQUEST_TIMEOUT` | `90` | Timeout applied to every Ollama request. |
| `OLLAMA_MAX_RETRIES` | `1` | Retries after the initial request. |
| `OLLAMA_RETRY_BACKOFF_SECONDS` | `0.5` | Base exponential backoff. |
| `OLLAMA_KEEP_ALIVE` | `30m` | Model lifecycle value sent to Ollama. |
| `OLLAMA_UNLOAD_ON_SHUTDOWN` | `false` | Requests generation-model unload at process shutdown. |
| `OLLAMA_MAX_CONNECTIONS` | `20` | Shared transport maximum connections. |
| `OLLAMA_MAX_KEEPALIVE_CONNECTIONS` | `10` | Shared transport idle keep-alive connections. |

`backend/app/core/config.py` also defines scoring, matching, extraction-version, batch, recommendation, and retrieval tuning. Treat changes to parser, schema, prompt,
model, vacancy, and matching versions as cache-invalidating changes.

## Local development

Requirements are Python 3.12 or newer and [uv](https://docs.astral.sh/uv/). Redis and PostgreSQL/pgvector are required for the normal queue/vector path. MSSQL is
optional when its backed features are not needed. Ollama is optional when both LLM and embedding features are disabled.

```bash
cp backend/.env.example backend/.env
cd backend
uv sync --frozen
```

Run the explicit migration for each configured database:

```bash
uv run python scripts/run_migrations.py --dialect postgres
uv run python scripts/run_migrations.py --dialect mssql
```

Start the API and worker in separate terminals from `backend/` so they share the same configured paths:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
uv run rq worker --url redis://localhost:6379/0 cv-processing
```

If `RQ_QUEUE_NAME` or `REDIS_URL` changes, pass the same values to the worker. The in-process fallback is a development containment path, not a substitute for a
worker in deployed environments.

The API exposes service discovery at `http://localhost:8000/`, dependency health at `http://localhost:8000/health`, and OpenAPI UI at
`http://localhost:8000/docs`.

## Docker Compose

Compose provides API, RQ worker, Redis, and PostgreSQL/pgvector services plus an explicit PostgreSQL migration profile. Before starting production-mode services,
provide deployment values through the shell or an ignored root `.env`, including unique API keys, a non-default PostgreSQL password, and trusted origins.

```dotenv
POSTGRES_PASSWORD=replace-with-a-unique-secret
RECRUITER_API_KEYS=["replace-with-a-generated-recruiter-secret"]
ADMINISTRATOR_API_KEYS=["replace-with-a-generated-administrator-secret"]
ALLOWED_ORIGINS=["https://recruiting.example.com"]
```

Start infrastructure, apply migrations, and then start the application processes:

```bash
docker compose up -d pgvector redis
docker compose --profile tools run --rm migrate-postgres
docker compose up -d api worker
```

The API and worker share `backend/uploads`, use the same queue and service configuration, wait for healthy Redis/PostgreSQL, and restart unless stopped. The worker
must retain access to that shared volume because RQ payloads contain only job IDs. The Compose stack expects Ollama on the Docker host by default.

Compose does not provision MSSQL. If MSSQL-backed features are enabled, supply `DB_*` variables to the API/worker through a deployment override and run the MSSQL
migration command as a separate release step.

## Verification commands

The repository policy requires explicit authorization before executing tests, builds, lint, migrations, or services. When authorized, the final verification set is:

```bash
cd backend
uv run pytest
uv run ruff check app tests
uv run python scripts/verify_schema_drift.py
```

```bash
docker compose config
docker compose build api worker migrate-postgres
```

After deployment, smoke-test public health, authenticated recruiter/admin routes, both upload and polling aliases, worker processing/retry behavior, request IDs,
error envelopes, configured rate limits, and Ollama-disabled fallback.

## Compatibility summary

- Existing API paths remain available, including upload, status, raw-text matching, and `/api/v1/candidates/*` aliases.
- Existing successful response fields remain; canonical identity, normalized resume data, job metadata, metrics, and errors were added without removing legacy fields.
- `document_parser.py` remains the stable extraction import facade, and legacy Ollama generation methods route through the shared executor.
- Legacy filename result lookup is preserved when the alias identifies exactly one canonical CV. Ambiguous aliases no longer select an unrelated candidate.
- Legacy job statuses adapt to canonical states. `error_details` remains present but never exposes a traceback.
- Top-level error `detail` remains alongside the canonical error envelope.
- PDF/DOCX-only uploads, production authentication, collision rejection, safe input limits, and default unknown-job HTTP 404 are intentional containment changes.
- Versioned extraction, matching, prompt, model, vacancy, and content identities deliberately prevent stale cache reuse.

## Remaining limitations

- OCR accuracy depends on scan resolution, orientation, contrast, language, handwriting, tables, columns, and embedded-image quality. Low-confidence output needs review.
- Password-protected/encrypted PDF and DOCX files are rejected; there is no password-submission or decryption workflow.
- Uncommon, highly visual, multilingual, or non-linear resume layouts can misassociate headings, employment dates, education, skills, and evidence.
- LLM output is not perfectly deterministic even with fixed prompts and low-temperature settings. Model/runtime changes can alter enrichment and explanations.
- LLM and embedding features depend on the configured Ollama models. Deterministic matching continues when LLM generation is disabled, but semantic depth is reduced.
- Structural upload validation is not malware scanning or content disarm and reconstruction. Public upload deployments need an isolated scanning stage.
- The application rate limiter is per process and socket peer. Multi-replica or proxied deployments need an authoritative shared gateway limit.
- API-key roles are coarse recruiter/administrator tiers, not tenant-aware user sessions, per-record authorization, or a credential-rotation service.
- Raw files contain PII. Retention settings are opportunistic and do not replace an audited deletion, legal-hold, backup, and access-governance process.
- API and worker require shared raw/result storage. The current Compose volume is host-local and needs shared durable storage for multi-host deployments.
- Jobs interrupted by a full Redis/worker outage may need an operational stale-job reconciler; automatic stale-record recovery is not yet provided.

See [Phase 7](backend/docs/phase7-documentation-and-final-verification.md) for the final changed-file map, compatibility assessment, verification status, and residual
risk register.

## Implementation change map

| Phase | Primary areas changed | Compatibility result |
| --- | --- | --- |
| 0 | Contracts, endpoint policy, stale tests, secret/data containment | Characterized existing paths and adapters before production changes. |
| 1 | Shared upload service, validation, retention, Docker packages | Kept both upload paths; intentionally limited file uploads to PDF/DOCX. |
| 2 | CV identity, repositories, cache keys, collision tests | Kept filename aliases when unambiguous; added collision protection. |
| 3 | Parser facade, extraction internals, normalized schemas, match contexts | Kept legacy fields/imports; added normalized data and removed duplicate work. |
| 4 | Processing records, queue service, RQ worker, job contracts | Kept polling/status adapters; added durable canonical job states. |
| 5 | Shared Ollama transport, generation/embedding services, lifecycle | Kept legacy generation methods; centralized network behavior. |
| 6 | Request/errors/auth/rate/CORS/lifespan, migrations, Docker | Kept success fields and error `detail`; intentionally enforced production controls. |
| 7 | README, final change/compatibility/limitations record, work status | Documentation-only; no runtime or API behavior changes. |

The exact per-phase file lists and decisions are retained in [workstatus.md](workstatus.md) and the phase documents below.

## Phase documentation

- [Phase 0 API contracts](backend/docs/phase0-api-contracts.md)
- [Phase 0 security containment](backend/docs/phase0-security-containment.md)
- [Phase 1 secure uploads](backend/docs/phase1-secure-uploads.md)
- [Phase 2 identity and caching](backend/docs/phase2-identity-and-caching.md)
- [Phase 3 structured CV processing](backend/docs/phase3-structured-cv-processing.md)
- [Phase 4 reliable background processing](backend/docs/phase4-reliable-background-processing.md)
- [Phase 5 standardized Ollama](backend/docs/phase5-standardize-ollama.md)
- [Phase 6 API and operational reliability](backend/docs/phase6-api-operational-reliability.md)
- [Phase 7 documentation and final verification](backend/docs/phase7-documentation-and-final-verification.md)

## Repository layout

```text
cv-analyzer/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── data/
│   │   ├── models/
│   │   ├── prompts/
│   │   ├── repositories/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   ├── docs/
│   ├── scripts/
│   │   └── migrations/
│   ├── tests/
│   ├── uploads/
│   ├── .env.example
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── uv.lock
├── docker-compose.yml
├── AGENTS.md
├── README.md
└── workstatus.md
```
