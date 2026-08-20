# backend/AGENTS.md

## Scope

This file applies to everything under `backend/`.

It extends the repository-root `AGENTS.md` with backend-specific architecture, coding, runtime, migration, testing, and integration rules.

Read the root `AGENTS.md` first.

---

# Backend Work Logging (`workstats.md`)

All backend modifications, features, bug fixes, database migrations, model updates, and configuration adjustments must be logged immediately upon completion into `workstats.md` at the repository root.

Follow the append-only rule: never delete, overwrite, or edit past log entries; add each change as a new sequential entry (`### Entry #XXX`) at the bottom of the file.

---

# Backend Mission

The backend is responsible for:

- secure CV upload and validation;
- document parsing;
- text normalization;
- structured resume extraction;
- confidence/quality evaluation;
- candidate persistence;
- vacancy processing;
- requirement evaluation;
- matching and scoring;
- hiring-risk generation;
- embeddings and semantic search;
- PostgreSQL/pgvector persistence;
- Redis/RQ background jobs;
- read-only MSSQL synchronization;
- optional Ollama generation/embedding enrichment;
- recruiter/admin APIs.

Correctness and explainability matter more than making one fixture pass.

---

# Backend Layout

Use the existing directory boundaries.

```text
backend/
├── AGENTS.md
├── app/
│   ├── api/
│   ├── core/
│   ├── data/
│   ├── models/
│   ├── prompts/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   └── main.py
├── scripts/
│   └── migrations/
├── tests/
├── uploads/
├── .env.example
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

Do not introduce a new architectural layer unless the responsibility clearly cannot fit an existing one.

---

# Responsibility Boundaries

## `app/api/`

Owns HTTP/WebSocket transport.

Appropriate responsibilities:

- route definitions;
- request parsing;
- request validation;
- dependency injection;
- access-control dependencies;
- response serialization;
- status-code mapping.

Keep route handlers thin.

Do not implement:

- CV extraction algorithms;
- matching logic;
- raw SQL business queries;
- Ollama transport;
- vector ranking;
- complex normalization;

inside route modules.

---

## `app/core/`

Owns cross-cutting runtime infrastructure and application policy.

Examples include:

- settings/configuration;
- authentication;
- authorization;
- cache infrastructure;
- request/correlation context;
- error handling;
- rate limiting;
- lifespan/startup/shutdown;
- database/Redis infrastructure;
- common operational policies.

Environment-specific settings belong here.

Do not scatter direct `os.getenv()` calls through feature code when a central setting is appropriate.

---

## `app/schemas/`

Owns stable typed contracts.

Use Pydantic models for durable structures such as:

- API requests/responses;
- normalized resumes;
- candidate structures;
- vacancy requirements;
- requirement assessments;
- evidence;
- matching results;
- hiring risks;
- job-state payloads.

Prefer typed semantic fields over text blobs.

Do not emit text such as `"5 years matched"` and later parse the number back out when a structured numeric field can exist.

---

## `app/models/`

Use models for persisted/domain entities according to existing conventions.

Before adding a model:

- confirm an existing schema/model does not already represent the concept;
- determine whether it belongs to persistence, API contracts, or internal domain state;
- avoid duplicating the same concept in multiple incompatible classes.

---

## `app/repositories/`

Owns persistence access.

Repository code should centralize:

- PostgreSQL queries;
- result persistence;
- processing-state persistence;
- training/configuration persistence;
- persistence-oriented retrieval.

Do not perform raw persistence queries inside API routes when a repository exists or should exist.

Keep domain policy out of repository code when it belongs in services/evaluators.

---

## `app/services/`

Owns orchestration and domain workflows.

Typical responsibilities include:

- document processing;
- extraction orchestration;
- normalization;
- matching;
- requirement evaluation;
- scoring;
- hiring-risk generation;
- search;
- embeddings;
- Ollama integration;
- queue orchestration;
- synchronization;
- recommendations;
- taxonomy.

A service should have a clear responsibility.

Do not let one service become the universal location for unrelated helpers.

---

## `app/prompts/`

Owns prompt definitions and prompt-versioned behavior.

When changing prompts:

- evaluate whether the prompt version must change;
- inspect caches that depend on prompt semantics;
- inspect structured response models;
- inspect tests;
- avoid placing schema-critical information only in free-form prompt prose.

Prompt changes are behavior changes.

---

## `scripts/migrations/`

Owns explicit PostgreSQL schema evolution.

Never use application startup as a substitute for production migrations.

Do not modify a historical migration to represent a new change.

Create a new migration.

Never create or run MSSQL migrations.

---

# CV Extraction Architecture

Extraction must be generalized and evidence-based.

Conceptual structure:

```text
ResumeExtractor
│
├── SectionDetector
├── ContactExtractor
│   ├── NameExtractor
│   ├── EmailExtractor
│   ├── PhoneExtractor
│   └── LocationExtractor
├── EmploymentExtractor
├── EducationExtractor
├── SkillsExtractor
├── ProjectExtractor
├── ExtractionRuleRegistry
├── ExtractionScorer
└── ResumeNormalizer
```

The exact implementation may differ, but preserve these separation principles.

## Extraction Rules

Do not hardcode production behavior for:

- one candidate;
- one filename;
- one company;
- one sentence;
- one resume layout;
- one test fixture.

Prefer reusable signals such as:

- section position;
- heading context;
- contact patterns;
- date ranges;
- role/company adjacency;
- bullet/list structure;
- typography/markdown structure if available;
- confidence scoring;
- cross-field consistency.

---

# `document_parser.py`

Treat `document_parser.py` as a compatibility facade when existing callers depend on it.

Preferred architecture:

```text
caller
  -> document_parser.py
  -> structured parser/extractor services
```

Do not force callers to import deep implementation modules solely because the internals were refactored.

Preserve compatible public entry points unless a breaking change is explicitly requested.

---

# Text Normalization

Normalize source text before higher-level extraction when possible.

Handle common issues systematically:

- repeated whitespace;
- HTML entities;
- malformed bullet characters;
- header/footer repetition;
- page artifacts;
- broken line wrapping;
- duplicated section titles;
- encoding noise.

Do not patch `"&amp;"` only in one output field if the normalization belongs earlier in the pipeline.

Fix the earliest correct layer.

---

# Evidence and Confidence

Important extraction and matching decisions should retain evidence.

Where supported, prefer structures containing:

- normalized value;
- raw/source evidence;
- source section;
- confidence;
- reason/rule identifier;
- ambiguity state.

A low-confidence extraction should not be presented as unquestionably correct.

---

# Matching Architecture

Treat matching as structured requirement evaluation.

Conceptually:

```text
vacancy requirements
       +
normalized candidate
       ↓
requirement evaluator
       ↓
per-requirement evidence
       ↓
mandatory failures / failure codes
       ↓
score / conclusion
       ↓
optional LLM explanation
```

Do not compute important hiring decisions by parsing presentation text.

---

# Requirement Assessments

Requirement-level results should be explainable.

Where the model supports it, retain:

- requirement;
- candidate evidence;
- vacancy/JD evidence;
- match state;
- conclusion;
- failure code;
- confidence.

Distinguish states such as:

- matched;
- not matched;
- not found;
- not assessable;
- unknown.

Do not fabricate candidate evidence.

---

# Hiring Risks

Hiring risks should be driven by structured evaluation signals and configured policies.

Preferred:

```text
failure_code
    -> risk policy registry
    -> structured hiring risk
```

Avoid:

```text
free-form message
    -> substring checks
    -> hardcoded risk branch
```

Adding a new risk should not require editing unrelated evaluator branches when policy configuration can represent it.

---

# PGVector and Semantic Search

Search must be dynamic and data-driven.

Do not implement search as:

- hardcoded example queries;
- fixed candidate IDs;
- one-off query text branches;
- static score overrides.

Separate:

1. query construction;
2. filtering;
3. embedding generation;
4. vector retrieval;
5. deterministic reranking;
6. presentation.

PGVector provides vector infrastructure; it should not own all ranking semantics.

## Embedding Compatibility

When changing an embedding model or dimension:

- inspect stored vector dimensions;
- inspect migration implications;
- inspect vector-generation code;
- inspect search code;
- inspect cache/version keys;
- determine whether re-embedding is required.

Never silently write vectors with incompatible dimensions.

---

# Ollama

All Ollama HTTP behavior must remain centralized.

Before adding Ollama functionality, search for the existing transport/client/service.

Do not create feature-specific clients.

Preserve:

- centralized model selection;
- timeout policy;
- retries;
- connection limits;
- response-size limits;
- generation locking;
- embedding batching;
- model lifecycle/unload behavior;
- shutdown cleanup.

Use operation-specific configuration rather than assuming one timeout fits tags, generation, embeddings, and unload.

## LLM Role

The LLM is an enrichment layer.

Do not make critical extraction or deterministic requirement evaluation depend entirely on model availability unless explicitly designed that way.

When Ollama is unavailable, follow existing fallback semantics.

---

# PostgreSQL

PostgreSQL/pgvector is writable application storage.

Use repository/database abstractions.

When changing schema:

1. create a migration;
2. update model/repository code;
3. update tests;
4. inspect schema-drift checks;
5. consider existing data migration/backfill;
6. consider rollback.

Do not mutate production schema implicitly on startup.

---

# MSSQL

MSSQL is strictly read-only.

Never execute:

- `INSERT`;
- `UPDATE`;
- `DELETE`;
- `MERGE`;
- `ALTER`;
- `CREATE`;
- `DROP`;
- write stored-procedure calls;

against MSSQL from this application unless the architecture is explicitly changed by the project owner.

Synchronization should read from MSSQL and write normalized copies/state into PostgreSQL.

---

# Redis and RQ

Redis supports:

- RQ queues;
- distributed locks;
- short-lived processing state;
- caches.

Keep queue payloads small.

Prefer queueing stable identifiers instead of large serialized document/extraction objects.

## Job State

Preserve canonical processing-state semantics.

Typical states:

```text
QUEUED
PROCESSING
RETRYING
COMPLETED
FAILED
UNKNOWN
```

Do not mix these with result outcomes such as:

```text
NEW_CV
REPROCESSED
CACHE_HIT
```

## Idempotency

Processing must tolerate duplicate enqueue attempts and retries.

Preserve:

- canonical identifiers;
- content hashes/versions;
- distributed execution locks;
- collision checks;
- retry-safe persistence.

---

# File Upload Security

Uploaded resumes are untrusted files containing sensitive PII.

Do not weaken existing validation.

Preserve as applicable:

- extension allowlist;
- MIME/signature validation;
- compressed-size limits;
- decompressed-size limits;
- PDF structural checks;
- DOCX ZIP/path safety;
- macro/external-link restrictions;
- atomic writes;
- path traversal protection.

Do not enable a legacy file format merely because a parser library can technically read it.

---

# API Errors

Use centralized structured error handling.

Do not leak:

- tracebacks;
- database internals;
- local filesystem paths;
- credentials;
- raw exception strings containing secrets.

Preserve request/correlation identifiers and established API error compatibility.

Map dependency outages appropriately.

---

# Authentication and Authorization

Routes should use existing access-control dependencies.

Do not bypass auth for convenience.

When adding a route, explicitly classify it as:

- public;
- recruiter;
- administrator;

according to existing project policy.

Admin access may include recruiter privileges; do not weaken the reverse boundary.

Candidate PII must remain protected.

---

# Cache and Semantic Versioning

Review cache validity when changing:

- parser behavior;
- extraction rules;
- schemas;
- prompts;
- LLM models;
- embeddings;
- vacancy normalization;
- matching;
- scoring;
- retrieval policy.

A behavior change may require:

- prompt version bump;
- extraction version bump;
- cache-key change;
- vector regeneration;
- result regeneration.

Do not reuse stale cached outputs under incompatible semantics.

---

# Python Conventions

Target Python 3.12+.

Use the existing `uv` workflow.

Use type hints for new/changed public interfaces where practical.

Prefer Pydantic for stable structured contracts.

Follow existing async architecture.

Do not block the event loop with heavy synchronous work in request handlers.

Move CPU/long-running workloads to existing background-processing paths where appropriate.

Follow Ruff configuration.

Current repository line-length policy is 200 characters.

---

# Dependency Management

Use:

```bash
uv add <package>
```

or the repository's established dependency workflow.

Keep `pyproject.toml` and `uv.lock` consistent.

Do not manually hand-edit lockfile internals.

Before adding a dependency, confirm the capability does not already exist.

---

# Setup

From `backend/`:

```bash
uv sync --frozen
```

Copy local configuration if needed:

```bash
cp .env.example .env
```

Do not commit `.env`.

---

# Run

API:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

RQ worker:

```bash
uv run rq worker --url redis://localhost:6379/0 cv-processing
```

If Redis URL or queue name is configured differently, use the configured values.

---

# Migrations

Run PostgreSQL migrations:

```bash
uv run python scripts/run_migrations.py
```

Schema drift verification:

```bash
uv run python scripts/verify_schema_drift.py
```

Do not execute migrations without explicit user authorization.

---

# Tests

Run all backend tests:

```bash
uv run pytest
```

Prefer targeted verification while developing:

```bash
uv run pytest tests/<relevant_test_file>.py
```

Lint:

```bash
uv run ruff check app tests
```

Do not run tests/lint without explicit user authorization.

---

## Release Gate Verification Protocol (`verify_release_gate.py`)

`scripts/verify_release_gate.py` orchestrates the complete 23-gate master release governance suite.

To avoid slow test cycles and wasteful CPU resource consumption:

- **Do NOT run `verify_release_gate.py` on every task or minor code edit.**
- Use narrow targeted tests (`uv run pytest tests/<relevant_test_file>.py`) during routine development.
- Avoid unnecessary runs because `verify_release_gate.py` executes 208+ test cases across 23 gates and takes ~30+ seconds.

### Exact Conditions Requiring `verify_release_gate.py` Execution:
1. The user explicitly requests release gate or production readiness verification.
2. You modify `scripts/verify_release_gate.py` or register a new release gate.
3. Performing final release governance validation before production deployment or version tagging.

---

# Test Philosophy

Many tests are literal, hardcoded regression cases.

Evaluate every test according to its actual logic.

Do not assume fixtures are dynamic templates.

When a test exposes a bug:

- identify the generalized production defect;
- fix the production layer;
- preserve the regression test;
- add broader cases if needed.

Avoid fragile tests based on:

- exact LLM wording;
- arbitrary sleep durations;
- private implementation details;
- ordering without a contract;
- unrelated candidate-specific strings.

---

# Integration Tests

Tests using live external services must remain clearly separated/marked.

Examples may include:

- PostgreSQL integration;
- Redis/RQ integration;
- MSSQL read-only integration;
- Ollama live tests.

Do not silently turn a unit test into a mandatory live-service test.

---

# Logging

Use existing logging infrastructure.

Useful operational fields include:

- request ID;
- correlation ID;
- job ID;
- CV/candidate ID;
- processing stage;
- duration;
- cache result;
- retry decision;
- external dependency state.

Do not log full sensitive resumes unnecessarily.

Never log credentials or authorization headers.

---

# Performance

Do not add concurrency, caching, or batching without understanding existing controls.

For local Ollama/document processing, uncontrolled parallelism can worsen latency and memory use.

Preserve bounded concurrency.

Prefer measured bottleneck fixes over speculative optimization.

---

# Refactoring

A backend refactor is justified when it:

- removes duplicated logic;
- removes candidate-specific hacks;
- centralizes configuration;
- strengthens service/repository boundaries;
- improves typed contracts;
- improves deterministic behavior;
- improves testability;
- preserves compatibility.

Avoid repository-wide rewrites when a smaller generalized fix exists.

---

# Backend Definition of Done

Before considering backend work complete, confirm as applicable:

- correct layer was changed;
- no candidate-specific production hack was added;
- schemas are structured and typed;
- API compatibility was preserved or intentionally changed;
- migrations exist for PostgreSQL schema changes;
- MSSQL remains read-only;
- Redis/RQ behavior remains idempotent;
- cache/version implications were handled;
- Ollama integration remains centralized;
- embedding dimensions remain compatible;
- tests were updated;
- authorized tests/lint were actually run;
- no unrelated code was changed;
- security/PII protections were preserved;
- changes were logged immediately to root `workstats.md` (append-only).

Never report a test, migration, or verification as successful unless it was actually executed.