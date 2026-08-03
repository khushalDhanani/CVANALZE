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
2. Reuse the pooled client and configured connection limits.
3. Apply `OLLAMA_REQUEST_TIMEOUT` to every HTTP operation.
4. Retry retryable connection, timeout, HTTP, invalid-JSON, and schema failures up to `OLLAMA_MAX_RETRIES` times after the initial attempt.
5. Wait `OLLAMA_RETRY_BACKOFF_SECONDS * 2^(attempt-1)` before each retry.
6. Map failures to typed Ollama errors and log operation, attempt, outcome, duration, and error type.
7. Record aggregate and per-operation request, success, failure, retry, timeout, and duration metrics.

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

Both single and batch embedding requests use the shared transport, timeout, retry policy, response schema, keep-alive policy, and pooled client. The prior local
30-second and 60-second clients are removed. Existing content/model cache keys and the short model-failure throttle remain unchanged.

## Model lifecycle

Generation and embedding payloads set the configured `OLLAMA_KEEP_ALIVE` value. CV processing no longer unloads the generation model after each candidate, so
concurrent and sequential jobs can reuse model state. At application shutdown the shared HTTP pool is always closed. An explicit unload is sent first only when
`OLLAMA_UNLOAD_ON_SHUTDOWN=true`.

`OllamaLLMService.unload_model` remains available for compatibility and controlled lifecycle use; normal CV processing does not call it.

An Ollama model is shared by every API/worker process using that server. In multi-process deployments, leave `OLLAMA_UNLOAD_ON_SHUTDOWN=false` unless shutdown is
coordinated across all Ollama consumers; unloading from one process can evict a model another worker is using.

## Metrics

Transport metrics are exposed additively under `system_stats.ollama_transport` in `GET /api/analytics/cache`. Existing cache analytics fields are unchanged.

## Configuration

| Setting | Default | Purpose |
| --- | ---: | --- |
| `OLLAMA_REQUEST_TIMEOUT` | `90` | Timeout applied uniformly to every Ollama operation |
| `OLLAMA_MAX_RETRIES` | `1` | Retries after the initial attempt |
| `OLLAMA_RETRY_BACKOFF_SECONDS` | `0.5` | Base exponential retry delay |
| `OLLAMA_KEEP_ALIVE` | `30m` | Model lifetime sent with generation and embedding requests |
| `OLLAMA_UNLOAD_ON_SHUTDOWN` | `false` | Explicitly unload the configured generation model during shutdown |
| `OLLAMA_MAX_CONNECTIONS` | `20` | Pooled-client maximum connections |
| `OLLAMA_MAX_KEEPALIVE_CONNECTIONS` | `10` | Pooled-client idle keep-alive connections |

Docker Compose forwards these settings to both the API and RQ worker, using the documented defaults when deployment environment values are absent.

## Regression coverage

Phase 5 tests characterize pooled-client reuse, configured timeout use, generation cache hits, connection retries, timeout exhaustion, malformed generated JSON,
Pydantic schema failures, unavailable-model mapping, embedding delegation, keep-alive payloads, explicit unload, and disabled-LLM fallback. Existing legacy generation
methods remain covered so they can be removed only after external consumers are audited in a future compatibility phase.
