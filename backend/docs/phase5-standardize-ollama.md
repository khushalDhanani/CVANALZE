# Phase 5 — Standardize Ollama

## Architecture

All Ollama HTTP traffic now passes through `OllamaTransport`, which owns one process-level pooled `httpx.Client`. The transport is the only module that knows the
Ollama endpoint paths. It provides common operations for model discovery, structured generation, embeddings, and explicit model unload.

The application boundaries remain:

- `OllamaLLMService` is the only generation service. Its legacy extraction and scoring methods remain available and delegate to one structured-generation executor.
- `EmbeddingService` is the only embedding service. Single and batch requests delegate to `OllamaTransport.embed` after the existing embedding-cache lookup.
- startup, health, and shutdown checks use `OllamaLLMService`; they do not create independent clients.

No public API path or existing response field was removed.

## Shared execution contract

The transport applies the following behavior to tags, generation, embeddings, and unload operations:

1. Build the operation payload from centralized helpers.
2. Acquire the in-process and shared file lock so API and RQ processes cannot overlap Ollama work.
3. Reuse one pooled client inside the logical operation and close it when the scope exits.
4. Apply operation-specific total deadlines; retries cannot reset or multiply the deadline.
5. Wait `OLLAMA_RETRY_BACKOFF_SECONDS * 2^(attempt-1)` before each retry.
6. Map failures to typed Ollama errors and log operation, attempt, outcome, duration, and error type.
7. Bound streamed response bytes, validate typed envelopes and returned model identity, and reject HTTP-200 error objects before use.
8. Unload every model touched by generation or embedding in `finally`, including failure paths.
9. Record aggregate and per-operation request, success, failure, retry, timeout, lock-wait, response-size, load, inference, unload, and duration metrics.

HTTP 404 responses for model-scoped requests become `OllamaModelUnavailableError` and are not retried. HTTP 408, 429, and 5xx responses are retryable. Generation
callers continue to return their existing `None` fallback after transport exhaustion, and embedding failures remain non-fatal to the matching pipeline.

## Structured generation

`extract_candidate_profile`, `call_qwen`, `call_qwen_dynamic`, and `run_optimized_match` remain compatibility methods. Each method selects its existing schema,
thinking directive, and inference options, then delegates to the same executor. That executor centralizes:

- version-aware `LLMCacheRepository` lookup and persistence;
- generation payload construction;
- Ollama envelope validation;
- Markdown-fence removal and structured JSON extraction;
- response-model validation;
- profiler timings and token metadata; and
- disabled-LLM fallback.

When LLM processing is enabled, valid cache hits do not contact Ollama. Invalid cached structures fall through to live generation. Disabling LLM processing retains
the prior contract and returns the method-specific fallback without consulting the generation cache or transport.

## Embeddings

Both single and batch embedding requests use the shared transport, total deadline, response schema, lifecycle scope, and pooled client. Inputs are deduplicated,
bounded chunks reuse one model scope, every vector is finite/nonzero with the configured dimension, and invalid batches never fan out into uncontrolled per-item calls.
Existing content/model cache keys and the short model-failure throttle remain unchanged.

## Model lifecycle

Generation and embedding payloads set a short configured `OLLAMA_KEEP_ALIVE` value only while one serialized logical operation is active. The operation unloads every
distinct model in `finally`, then closes the HTTP pool. Embedding chunks reuse the model before the single final unload, avoiding load/unload cycles inside loops.
Application shutdown unloads both configured model names when enabled and always closes any remaining client.

`OllamaLLMService.unload_model` remains available for compatibility and controlled lifecycle use.

An Ollama model is shared by every API/worker process using that server. The shared file lock coordinates this repository's API and worker consumers. External Ollama
consumers must use equivalent coordination if they share the same host server.

## Metrics

Transport metrics are exposed additively under `system_stats.ollama_transport` in `GET /api/analytics/cache`. Existing cache analytics fields are unchanged.

## Configuration

| Setting | Default | Purpose |
| --- | ---: | --- |
| `OLLAMA_REQUEST_TIMEOUT` | `60` | Compatibility timeout for the shared client |
| `OLLAMA_CONNECT_TIMEOUT_SECONDS` | `3` | Connection timeout |
| `OLLAMA_TAGS_TIMEOUT_SECONDS` | `3` | Tags total deadline |
| `OLLAMA_GENERATE_TIMEOUT_SECONDS` | `60` | Generation total deadline |
| `OLLAMA_EMBED_TIMEOUT_SECONDS` | `30` | Complete embedding-batch deadline |
| `OLLAMA_UNLOAD_TIMEOUT_SECONDS` | `10` | Unload deadline |
| `OLLAMA_MAX_RETRIES` | `0` | Retries after the initial attempt |
| `OLLAMA_RETRY_BACKOFF_SECONDS` | `0.5` | Base exponential retry delay |
| `OLLAMA_KEEP_ALIVE` | `1m` | Maximum intra-operation residency before explicit unload |
| `OLLAMA_UNLOAD_ON_SHUTDOWN` | `true` | Unload configured generation and embedding models during shutdown |
| `OLLAMA_MAX_CONNECTIONS` | `1` | Pooled-client maximum connections |
| `OLLAMA_MAX_KEEPALIVE_CONNECTIONS` | `1` | Pooled-client idle keep-alive connections |
| `OLLAMA_MAX_RESPONSE_BYTES` | `4194304` | Maximum response body |
| `OLLAMA_LOCK_FILE` | `uploads/.locks/ollama.lock` | API/worker cross-process lock |
| `OLLAMA_LOCK_TIMEOUT_SECONDS` | `65` | Lock acquisition timeout |
| `OLLAMA_EMBED_BATCH_SIZE` | `10` | Inputs per bounded embedding chunk |
| `OLLAMA_EMBEDDING_EXPECTED_DIMENSION` | `768` | Required vector dimension |

Docker Compose forwards these settings to both the API and RQ worker, using the documented defaults when deployment environment values are absent.

## Regression coverage

Phase 5 tests characterize pooled-client reuse, configured timeout use, generation cache hits, connection retries, timeout exhaustion, malformed generated JSON,
Pydantic schema failures, unavailable-model mapping, embedding delegation, keep-alive payloads, explicit unload, and disabled-LLM fallback. Existing legacy generation
methods remain covered so they can be removed only after external consumers are audited in a future compatibility phase.
