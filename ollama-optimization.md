# Ollama Optimization Plan

Status: **Implemented — runtime verification awaiting explicit authorization**  
Audit date: 2026-08-03  
Target: Python/FastAPI backend and lightweight Docker development on an Apple Silicon Mac with 8 GB unified memory

The approved plan has been implemented. No tests, services, builds, model pulls, live Ollama calls, or migrations were run because those actions require separate
explicit authorization under the repository policy.

## 1. Architecture impact analysis

### Current architecture

All direct Ollama HTTP traffic is already centralized in `backend/app/services/ollama_transport.py`. The transport owns one shared `httpx.Client`, retry and timeout
behavior, request payload builders, typed transport errors, basic envelope validation, logging, and metrics. Generation is routed through
`OllamaLLMService`; embeddings are routed through `EmbeddingService`. No second production Ollama HTTP client or direct `/api/*` request was found.

The current wire-level operations are:

| Ollama operation | Central method | Consumers and call paths | Current normalization | Current lifecycle |
| --- | --- | --- | --- | --- |
| `GET /api/tags` | `OllamaTransport.get_tags()` | startup model verification, root health, analysis health, available-model lookup | Pydantic envelope with a list of model names | Does not load a model; pooled client closes only at application/test shutdown |
| `POST /api/generate` | `OllamaTransport.generate()` | optimized matching; compatibility profile, Qwen, and dynamic-generation methods | outer generation envelope, structured JSON extraction, then endpoint-specific Pydantic schema | sends configured `keep_alive`; no per-operation unload |
| `POST /api/embed` | `OllamaTransport.embed()` | CV processing, vacancy prefiltering/sync, candidate search, domain/taxonomy embeddings, performance batching, RQ vacancy tasks | Pydantic envelope plus input/output count and non-empty-vector checks | sends configured `keep_alive`; embedding model is never explicitly unloaded |
| `POST /api/generate` with `keep_alive: 0` | `OllamaTransport.unload()` | explicit compatibility method and optional generation-model shutdown cleanup | currently accepts any JSON object as success | shutdown unload is disabled by default and does not unload the embedding model |

### High-priority findings

1. **Models stay resident too long for an 8 GB Mac.** The base setting is `OLLAMA_KEEP_ALIVE=30m`; the lightweight override still uses `2m`. The generation model is
   unloaded only at shutdown when an off-by-default flag is enabled, and the embedding model has no shutdown unload path.
2. **There is no global Ollama concurrency gate.** The shared client permits 20 connections, `PerformanceService.generate_embeddings_batch_async()` defaults to five
   concurrent calls, and API and RQ worker processes can call the same host Ollama server simultaneously.
3. **A timeout can consume much longer than its advertised value.** The 90-second timeout is applied per attempt and one retry is enabled, so one logical request can
   occupy Ollama for roughly 180 seconds plus backoff. Timeout, tags, embed, generate, and unload also share the same budget.
4. **Embedding fallback amplifies load.** Batches are split into groups of ten. If a batch fails validation, every item is retried individually. Candidate migration,
   candidate-search fallback, taxonomy creation, and synchronous RQ fallback also contain loops that can repeatedly load/call a model.
5. **Response validation is incomplete.** Generation does not require `done=true`, check the returned model, reject an Ollama `error` field in an HTTP 200 response, or
   bound response size. Embeddings do not validate finite numbers, consistent dimensions, expected model, unit-length tolerance, or maximum vector dimensions. Unload
   treats an empty or unrelated object as success. Tag names are not stripped, rejected when empty, or deduplicated.
6. **Client and response cleanup is process-scoped.** The shared client is correctly closed by FastAPI lifespan and the focused Phase 5 fixture, but not by every test
   module or manual script. Response cleanup is implicit in `httpx.Client.request()` rather than enforced in a `finally` block.
7. **Tests are mocked individually, not denied network globally.** Most Ollama tests use mocks, but there is no suite-wide guard that makes an accidental live Ollama call
   fail immediately. The manual `backend/test_llm.py` script is live by design and has no explicit opt-in guard.
8. **The analysis health route can perform two tag requests.** If the first model-list request returns an empty list, it immediately calls the health method and repeats
   `/api/tags`.

### Medium-priority findings

- The local profile disables generation and embeddings by default, which is the safest default, but enabling them inherits the 4B generation model and 90-second retry
  policy unless the operator supplies overrides.
- Optimized matching requests an 8K context and up to 4K output tokens. That is expensive on a small model and prolongs memory residency.
- Cache hits correctly prevent many generation and embedding calls, but on-the-fly candidate search can still generate one embedding per missing candidate inside a
  result loop.
- Startup verification and health checks are lightweight tag calls, but repeated polling still consumes sockets and log/metric volume.
- A Python `gc.collect()` cannot release Ollama model memory because Ollama runs as a separate host process. The backend must request unload; Python cleanup should be
  limited to response/prompt references and should not add costly collection to every ordinary code path.

### Required lifecycle interpretation

“Unload after every request” and “avoid repeated model loading in loops” conflict if “request” means each low-level batch chunk. The implementation should define one
**logical Ollama operation scope**:

1. Acquire the single local Ollama execution lock.
2. Open/reuse the one centralized HTTP client inside that scope.
3. Perform one generation, or all bounded chunks belonging to one embedding batch.
4. Normalize and validate every wire response before exposing it to callers.
5. In `finally`, explicitly unload every model used by the scope, close response objects, close/reset the shared client, and release the lock.

This guarantees cleanup after success, timeout, invalid JSON, schema failure, or unavailable-model errors while loading each model at most once per logical batch. Tag
requests do not load a model, so they require response/client cleanup but no fake unload call.

The official Ollama API documents `keep_alive: 0` as immediate unload behavior for generation, and documents final generation fields such as `done` and `done_reason`:
[Ollama model lifecycle](https://docs.ollama.com/faq), [generate contract](https://docs.ollama.com/api/generate). The embed endpoint supports arrays of inputs, so loop
work should be consolidated into bounded batches: [embed contract](https://docs.ollama.com/api/embed).

### Apple Silicon model decision

Keep AI disabled by default in `docker-compose.local.yml`. When explicitly enabled, use:

- Generation: `qwen3:1.7b` (Q4_K_M, approximately 1.4 GB) as the local default. Use `qwen3:0.6b` (approximately 523 MB) only for smoke tests where lower extraction and
  scoring quality is acceptable. Keep the production-oriented base model independently configurable.
- Embeddings: retain `nomic-embed-text` (approximately 274 MB) to preserve the existing 768-dimensional pgvector/cache contract. A model switch would require a new
  embedding version and controlled reindex, not an in-place replacement.

These sizes are from the official Ollama model registry: [Qwen3 tags](https://ollama.com/library/qwen3/tags),
[nomic-embed-text](https://ollama.com/library/nomic-embed-text). No model will be downloaded automatically by Docker or tests.

## 2. Files modified

### Required production and configuration changes

- `backend/app/services/ollama_transport.py` — operation scope, serialization, bounded responses, strict typed envelopes, cleanup, unload, and total-deadline handling.
- `backend/app/services/llm_service.py` — consume normalized generation results, remove duplicated tag call behavior, reduce local prompt budgets through configuration,
  and guarantee the model scope for every compatibility and primary generation method.
- `backend/app/services/embedding_service.py` — validated batch operation, one unload per logical batch, finite/dimension checks, and removal of individual-call fallback.
- `backend/app/core/lifecycle.py` — close any remaining transport and unload both configured models as shutdown defense in depth.
- `backend/app/core/config.py` — bounded operation timeouts, one-call concurrency, lock, response-size, embedding-dimension, and local token/context settings.
- `backend/.env.example` — document every new lifecycle and resource setting with conservative values.
- `docker-compose.local.yml` — local 1.7B model, one concurrent Ollama operation, no retries, strict deadlines, zero long-lived model residency, and shared lock path.
- `docker-compose.yml` — pass through new settings without weakening the production-oriented defaults.

### Loop and caller containment

- `backend/app/services/performance_service.py` — remove the five-call default and delegate to the shared batch API.
- `backend/app/services/vector_migration_service.py` — collect uncached candidate texts and issue bounded batches instead of one live call per candidate.
- `backend/app/services/candidate_search_service.py` — do not generate missing candidate embeddings inside the result loop; batch or defer indexing.
- `backend/app/services/domain_embedding_service.py` and `backend/app/services/dynamic_taxonomy_service.py` — batch related taxonomy terms in one model scope.
- `backend/app/core/tasks.py` and `backend/app/services/embedding_sync_service.py` — ensure synchronous/RQ vacancy paths reuse the shared batch boundary.
- `backend/app/api/analysis.py` — perform one normalized tags request per health check.

### Tests and documentation

- Create `backend/tests/conftest.py` — globally deny real Ollama network access by default, close the transport after every test, and serialize explicitly marked live tests.
- Update `backend/tests/test_phase5_ollama_standardization.py` — response contracts, lock behavior, total deadlines, unload-in-finally, response/client closure, and no
  parallel calls.
- Update `backend/tests/test_qwen_llm_service.py` — required final envelope fields, model-scope cleanup, and configured token/context limits.
- Update `backend/tests/test_vacancy_embeddings.py` and `backend/tests/test_enterprise_performance.py` — one batched call and deterministic isolation.
- Update `backend/test_llm.py` — require an explicit live-test environment flag and guarantee cleanup.
- Update `backend/pyproject.toml` — register `ollama_live`/`integration` markers and keep default pytest execution offline and single-process for live tests.
- Update `README.md` and `run.md` — lightweight opt-in workflow, model sizes, host Ollama limits, timeout behavior, and cleanup guarantees.
- Update `workstatus.md` — implementation outcome, files changed, verification, remaining risks, and decisions.

No unrelated files or API contracts were changed.

## 3. Implementation plan

### Step 1 — Strengthen the central wire contracts

- Reject an HTTP 200 response containing a non-empty `error` field.
- Read responses with an explicit byte limit and close each `httpx.Response` deterministically.
- Normalize model names by trimming whitespace and compare the returned model with the requested model when the response supplies it.
- Require non-streaming generation completion (`done=true`), non-negative usage metrics, a recognized completion reason, and non-empty structured content before inner
  JSON extraction and endpoint-specific Pydantic validation.
- Require embedding output count to match input count; require non-empty, same-length vectors containing only finite floats; enforce a configurable maximum and expected
  dimension; reject zero vectors and optionally record unit-length drift without silently changing values.
- Add a typed unload envelope and require confirmed completion instead of treating any object as success.
- Strip, reject empty, and deduplicate model names in the tags envelope.
- Preserve existing caller return types and fallback behavior.

### Step 2 — Add one serialized logical-operation scope

- Add one in-process re-entrant lock plus a `filelock`-based cross-process lock. The local API and RQ worker already share the uploads volume, so both can use one lock
  file. Tests use a temporary lock path.
- Default local maximum concurrent Ollama model operations to one. A bounded lock-acquisition timeout must return a typed retryable transport error instead of waiting
  indefinitely.
- Hold the lock across all chunks in one embedding batch so no generation, embedding, worker, or API call can overlap locally.
- Track models touched by the operation. In `finally`, request unload for each distinct model even when the primary call times out or validation fails.
- Make cleanup non-recursive: the unload request uses a private transport path that does not open another model scope.
- Close/reset the single shared client after the logical scope. It remains pooled across the bounded requests inside that scope and cannot leak between tests.
- Keep lifespan shutdown cleanup for abnormal/incomplete scopes and unload both generation and embedding model names when distinct.

### Step 3 — Use total deadlines and conservative local generation budgets

- Preserve `OLLAMA_REQUEST_TIMEOUT` as a compatibility fallback, then add operation-specific connect/tags/generate/embed/unload timeouts.
- Enforce a total logical-operation deadline rather than resetting the full timeout on each retry.
- Lightweight defaults: 3-second tags/connect timeout, 60-second generation deadline, 30-second embed deadline, 10-second unload deadline, and zero retries. Exact values
  remain configurable for unusually slow documents.
- Cap local generation at a 4K context. Use up to 1K output tokens for profile/analysis calls and 2K for optimized matching, subject to response-schema regression tests.
- Keep temperature at zero and retain JSON-schema structured output.
- Record lock wait, load duration, inference duration, unload duration/result, response bytes, attempts, and timeout reason without logging prompts, CV text, or raw model
  output.

### Step 4 — Remove call multiplication

- Replace batch-to-individual fallback with a bounded split strategy: if a batch fails because of size, bisect it to a configured minimum; if schema/model/timeout
  validation fails, stop and return explicit failed indices rather than issuing N individual calls.
- Deduplicate identical embedding inputs by content hash before calling Ollama, then restore original ordering.
- Batch uncached candidate migration/search inputs, vacancy inputs, and taxonomy terms through the public `EmbeddingService` API. Do not call private embed helpers from
  higher-level services.
- Keep cache checks before the lock/model load. Persist only fully validated vectors.
- Avoid loading the generation model in vacancy loops; optimized matching remains one call for the prefiltered vacancy set.

### Step 5 — Apply the lightweight Docker and host policy

- Retain the current four-service local memory/CPU limits, single RQ worker, disabled warmup, native-first parsing, and AI-disabled default.
- When local AI is opted in, set `qwen3:1.7b`, `nomic-embed-text`, one application Ollama operation, one client connection, no retries, and the strict deadlines above.
- Keep generation and embeddings serialized so the 1.4 GB generation model and 274 MB embedding model are not intentionally resident together.
- Do not add an Ollama container or automatic model pull. Ollama uses host unified memory and is outside Docker memory limits.
- Document host Ollama settings `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`, and immediate/short keep-alive as an operator requirement for the local profile.
- Preserve production overrides; do not silently replace a deployed model or invalidate stored embeddings.

### Step 6 — Make the test suite offline and non-parallel by default

- Add a suite-wide autouse guard that fails any unmocked request to the configured Ollama host.
- Default `LLM_ENABLED=false` and `EMBEDDING_ENABLED=false` for ordinary tests; tests enabling either feature must install a mock transport explicitly.
- Close/reset the transport, locks, metrics, and failed-model throttle state after every test.
- Mark live tests `ollama_live` and require both an explicit environment opt-in and a locally installed model. Live tests run serially and never under pytest-xdist.
- Add a two-thread and a two-process contention test proving maximum observed Ollama concurrency is one.
- Add regression tests for unload on success, timeout, invalid JSON, schema failure, model-not-found, and batch failure; assert unload failure is visible in metrics/logs and
  the client is still closed.
- Keep full-suite external systems mocked by default. No test may pull a model.

### Step 7 — Compatibility and rollout

- Preserve service method signatures, API paths, successful response fields, cache keys, and disabled-LLM fallbacks.
- Keep legacy generation methods routed through the common scope. Do not remove them without a separate compatibility decision.
- Treat a local model change as configuration only. Generation cache keys already include the model; embedding keys include the model and therefore remain isolated.
- Deploy the lifecycle/validation boundary first, then loop batching, then local defaults. Each stage must pass focused tests before the next stage.
- Model pulls, live Ollama calls, Docker builds/startup, and migrations remain separate explicit authorization gates.

## 4. Code changes

- Added strict typed tags, generation, embedding, and unload envelopes; bounded streamed response reads; HTTP-200 error rejection; requested/returned model matching;
  finite and dimensional vector validation; and normalized structured-output validation.
- Added a thread lock plus shared file lock, total operation deadlines, response/client cleanup, unload-in-`finally`, and transport metrics for lock wait, response bytes,
  model load, inference, and unload duration.
- Consolidated embedding chunks under one model scope, deduplicated inputs, removed per-item failure fan-out, and batched higher-level migration, search, taxonomy,
  performance, vacancy, and RQ workflows.
- Added conservative configuration, the opt-in `qwen3:1.7b` local model, one connection, zero default retries, explicit host Ollama guidance, and offline pytest guards.
- Preserved API response contracts, service compatibility methods, deterministic fallbacks, cache versioning, and the existing `nomic-embed-text` vector contract.

## 5. Verification checklist

Static inspection confirmed no second production Ollama HTTP client and `git diff --check` passed. The following runtime verification still requires explicit
authorization:

- Verify all production Ollama traffic still passes only through `OllamaTransport`.
- Verify tags, generate, embed, and unload accept valid documented responses and reject malformed, oversized, incomplete, mismatched-model, non-finite, wrong-dimension,
  and HTTP-200-with-error responses.
- Verify every model-bearing logical operation attempts unload and closes its client on success and every failure path.
- Verify one embedding batch loads/unloads once, preserves order, deduplicates inputs, and never falls back to uncontrolled per-item requests.
- Verify simultaneous API/worker/thread/process calls never exceed one local Ollama operation.
- Verify total deadlines cannot be multiplied by retries and lock waits are bounded.
- Verify ordinary pytest runs cannot contact Ollama; live tests require explicit opt-in and run serially.
- Run focused Ollama, embedding, match, vector-sync, and performance tests with external systems mocked.
- Run the complete pytest suite with external systems mocked, then Ruff lint/format checks and `git diff --check`.
- With separate live authorization, run one generation and one embedding batch on `qwen3:1.7b` and `nomic-embed-text`; confirm models disappear from resident memory after
  each logical operation and record peak host/Docker memory.
- With separate Docker authorization, validate both Compose configurations and confirm the lightweight stack remains within its current container limits.
- Do not run migrations; none are expected for this optimization.

## 6. Any refactoring performed

- Kept `document_parser.py` and unrelated processing code untouched.
- Refactored domain terms, candidate migration/search, vacancy synchronization, performance batching, and RQ vacancy synchronization to reuse the public batch boundary.
- Retained the centralized transport and compatibility methods; no duplicate client, alternate executor, API break, or migration was introduced.
