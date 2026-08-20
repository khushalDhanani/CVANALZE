# Hardcoded Configuration Remediation Design

**Date:** 2026-08-20

**Status:** Approved in chat

**Scope:** Deployment configuration, runtime settings, queueing, storage paths, scoring policy, frontend runtime configuration, hardcoding governance, and repository hygiene

## Objective

Remove material hardcoded values that bypass, contradict, or silently override runtime configuration while preserving public API compatibility and safe local-development defaults.

## Guiding decisions

1. Production configuration fails closed when required endpoints, credentials, trusted origins, or build metadata are absent.
2. Local development retains explicit loopback services and disposable credentials through the local Compose override, not the production base file.
3. Existing configuration fields become authoritative. Call sites must not substitute conflicting literals.
4. Unsupported CV-processing concurrency remains one until actual concurrent execution is implemented.
5. Stable protocol constants, HTTP status codes, MIME types, schema identifiers, and versioned emergency-policy defaults remain code constants.
6. Existing API paths and successful response shapes remain compatible.

## Architecture and changes

### Production and local deployment boundaries

The base `docker-compose.yml` remains production-oriented. It will no longer inject default PostgreSQL credentials, fixed application database URLs, fixed Redis URLs, a localhost CORS origin, or empty authentication credentials. Required production values will be supplied explicitly and validated by application settings.

Database host-port publication moves to the local override. Production services communicate over the Compose network or through explicitly configured managed-service URLs. The local override retains loopback bindings and local disposable service configuration.

Authentication validation will require a secure signing key and at least one recruiter or administrator API key when authentication is enabled in a production-like environment. Trusted CORS origins will also be required in that mode.

### Performance profiles

The 16 GB and 32 GB profiles currently advertise CV-processing concurrency that the application rejects. Their `CV_PROCESSING_CONCURRENCY` values will remain `1`. Parser and model resource settings may continue to scale independently where the runtime already consumes them.

The unused `MAX_CONCURRENT_LLM_WORKERS` setting will be removed from settings, Compose profiles, environment examples, and documentation as a no-op. This remediation will not introduce a new concurrent LLM execution model.

### Queue configuration

All queue producers and consumers will use the shared queue-name settings. Shadow-validation enqueueing will use `RQ_SHADOW_QUEUE_NAME` rather than a literal queue name.

Shadow retry count, retry interval, and job timeout will use explicit settings rather than embedded numeric values. Production behavior will retain current defaults unless overridden.

The primary queue name remains configurable. Validation will enforce only real invariants; it will not pretend a setting is configurable and then reject every value except its default. Single-slot worker execution remains an explicit invariant.

### Storage paths

Path defaults will be derived once from a canonical data root:

- local default data root: `backend/uploads`;
- upload root defaults to the data root itself;
- results default to `<uploads>/results`;
- locks default to `<data-root>/.locks`;
- training data defaults to `<data-root>/training_data`.

Explicit environment overrides remain supported. Derivation will occur through settings validation so programmatic settings overrides and environment-based configuration behave identically. The duplicated `TRAINING_DATA_DIR` declaration will be removed.

Existing data will not be deleted or moved automatically. Result and upload resolution will retain read-only compatibility with the legacy nested `uploads/uploads` location so prior files are not orphaned. All new writes will use the canonical paths.

### Scoring policy

`zero_skills_score_cap` will flow through the typed policy snapshot into `ScoringConfig`. Runtime matching will consume the active database or tenant value instead of resetting it to `40.0`.

Fallback defaults remain centralized in the emergency bundled policy factory. Direct-call defaults that production callers always override may remain only when they match canonical fallback configuration and are covered by tests.

### Frontend runtime configuration

Loopback API URLs remain available only in development. Production builds will require `EXPO_PUBLIC_API_URL` and fail clearly when it is missing.

Polling behavior will have one frontend authority. Unused backend-only frontend polling settings will be removed unless they are exposed through an existing typed API contract. The maximum polling duration will align with the backend job-timeout contract, and queue polling will stop deterministically instead of wrapping its attempt counter.

### Version metadata

`APP_VERSION` becomes the canonical application version. Compatibility access through `VERSION` will remain available without creating a second independently configurable value.

`GIT_SHA` will be injected by the build or deployment environment and required in production-like environments. In local development, an absent value will report explicit `unknown` metadata rather than a plausible stale commit.

### Redis operational settings

Redis socket-connect timeout, operation timeout, health-check interval, and relevant lock blocking timeouts will be settings-backed. API cache, queue submission, background jobs, and scheduler clients will consume consistent values unless a deliberately shorter probe timeout is given a separate named setting.

### Configuration and governance cleanup

The documented but unused `RQ_DEVELOPMENT_FALLBACK_ENABLED` flag will be removed because no in-process fallback exists in the current queue architecture.

Hardcoding baseline approvals will identify exact findings using file, category, line, and stable content fingerprint. File-wide category approvals will no longer suppress future findings.

Tracked editor settings will not contain developer-specific absolute paths, candidate/result filenames, or broad command auto-approval entries. Operational documentation will use sanitized MSSQL placeholders rather than an internal IP or privileged login example.

## Error handling

- Missing production credentials, origins, service URLs, or required metadata fail settings validation with actionable messages.
- Missing production frontend API configuration fails during configuration initialization rather than issuing requests to loopback.
- Queue configuration mismatches fail at startup or enqueue time with the configured queue name in the error context.
- Existing stored results remain readable; no destructive migration is part of this change.

## Compatibility impact

- Public HTTP routes and successful response fields remain unchanged.
- Local development remains supported through `docker-compose.local.yml` and `.env.example`.
- Production deployments relying on insecure implicit defaults must provide explicit configuration after this change.
- Existing queue defaults remain the same, but custom queue names begin working consistently.
- Existing scoring output may change only where an active policy specifies a non-default zero-skills cap; this is the intended correction.

## Verification strategy

Tests will be written before implementation changes for:

1. production settings rejection and local settings acceptance;
2. canonical path derivation and explicit path overrides;
3. custom primary and shadow queue names;
4. zero-skills policy propagation;
5. version and Git metadata behavior;
6. frontend production API URL enforcement and bounded polling;
7. exact hardcoding-baseline matching;
8. Compose profile compatibility through rendered configuration.

After implementation, the narrowest relevant backend and frontend tests, hardcoding audit scripts, and `docker compose config` rendering should be executed. Execution requires explicit user authorization under repository policy.

## Non-goals

- Implementing parallel CV workers or a new LLM concurrency subsystem.
- Moving or deleting existing uploaded CVs or results.
- Replacing the current configuration architecture wholesale.
- Changing extraction or matching product semantics beyond honoring the configured zero-skills cap.
- Running the full release gate unless separately requested by the user.

## Full-audit extension

The repository-wide audit identified material hardcoding beyond deployment configuration. The remediation therefore also covers extraction heuristics, operational result caps, frontend/backend capability drift, and audit completeness. This extension preserves the original compatibility and emergency-fallback decisions.

### Extraction policy and registries

`ResumeFieldExtractor` will resolve one immutable `ExtractionPolicy` at the start of an extraction. Layout windows, candidate/name/title/company length gates, score bonuses, fallback confidences, result caps, and junk-item thresholds will come from that snapshot. Section aliases, field-label aliases, present-role terms, honorifics, seniority prefixes, academic/identity labels, project/skill labels, synthetic filename terms, and supported social-link patterns will come from governed rule configuration or versioned baseline data exposed through `DynamicGeoAndHeadingService`.

Stable syntax remains code-owned: regular-expression operators, JSON field names, schema keys, Markdown delimiters, email/URL protocol grammar, and date parsing primitives. Fabricated entity values such as `Position`, `Organization`, and `Project` will be replaced by nullable values plus explicit extraction provenance.

### Operational and presentation policy

Search, taxonomy, recommendation, talent-graph, cache, pagination, prompt-context, and evidence-display caps will use typed policy/settings fields rather than call-site literals. Human-readable recruiter guidance remains versioned presentation policy and is not parsed downstream.

### Backend capabilities contract

The backend will expose an additive authenticated capabilities response containing upload formats and size, job timeout and polling guidance, similarity bounds and bands, batch choices, enabled pipeline stages, parser/model metadata, and build metadata. The frontend will consume this response when available and retain only explicit development/emergency fallbacks. Public routes and existing successful fields remain unchanged.

### Complete hardcoding governance

The audit will scan backend application/core/services, frontend runtime code, Compose and environment profiles, while excluding tests, migrations, generated artifacts, protocol constants, and versioned emergency policy through exact identities. Baseline approvals require file, line, category, normalized snippet fingerprint, owner, and justification. Scanner execution must use the repository Python 3.12 environment.
