# AGENTS.md

## Purpose

This file defines repository-wide instructions for AI coding agents working on CV Analyzer.

CV Analyzer is a monorepo containing:

- a Python/FastAPI backend for CV ingestion, extraction, normalization, search, matching, scoring, synchronization, and recruiter/admin APIs;
- an Expo/React Native frontend for recruiter-facing workflows;
- PostgreSQL/pgvector for writable application and vector data;
- Redis/RQ for queues, locks, processing state, and caching;
- read-only MSSQL integration for enterprise recruiting/taxonomy data;
- optional local Ollama generation and embedding services.

These instructions apply to the entire repository unless a more specific nested `AGENTS.md` exists.

---

## Instruction Precedence

When working on a file, follow instructions in this order:

1. The user's explicit task.
2. The nearest `AGENTS.md` in the file's directory hierarchy.
3. This root `AGENTS.md`.
4. Existing code conventions and documented architecture.

Expected module-specific files:

```text
AGENTS.md
backend/AGENTS.md
frontend/AGENTS.md
```

Backend-specific implementation rules belong in `backend/AGENTS.md`.

Frontend-specific implementation rules belong in `frontend/AGENTS.md`.

---

## Before Starting Any Task

Before changing code:

1. Read this `AGENTS.md`.
2. Read the nearest nested `AGENTS.md`, if one exists.
3. Read `workstatus.md` when present.
4. Inspect the relevant implementation before proposing changes.
5. Search for existing helpers, schemas, services, repositories, components, tests, configuration, and compatibility adapters related to the task.
6. Identify public contracts and downstream consumers before modifying shared behavior.
7. Prefer understanding the existing execution path over creating a parallel implementation.

For non-trivial changes, understand the complete flow first:

```text
input
  -> API/UI boundary
  -> validation
  -> service/orchestration
  -> extraction/evaluation
  -> persistence/cache
  -> response/presentation
```

Do not fix only the visible symptom when the defect originates earlier in the pipeline.

---

## Scope Discipline

- Modify only files necessary for the requested task.
- Do not refactor unrelated code.
- Do not reformat unrelated files.
- Do not rename public APIs, schemas, routes, fields, components, or database objects without a clear requirement.
- Do not silently remove compatibility behavior.
- Keep diffs focused and reviewable.
- Reuse existing abstractions before adding new ones.
- Do not introduce a second implementation of functionality already centralized elsewhere.
- Remove obsolete code only after confirming it has no runtime, test, migration, compatibility, or operational dependency.

When cleanup is part of the task, verify references before deleting files or symbols.

---

# Repository Architecture

## High-Level Layout

```text
cv-analyzer/
├── AGENTS.md
├── README.md
├── workstatus.md
├── docker-compose.yml
├── docker-compose.local.yml
│
├── backend/
│   ├── AGENTS.md
│   ├── app/
│   ├── docs/
│   ├── scripts/
│   ├── tests/
│   ├── uploads/
│   ├── .env.example
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── uv.lock
│
└── frontend/
    ├── AGENTS.md
    ├── src/
    └── package.json
```

---

# Cross-Layer Architecture

The repository separates transport, domain logic, persistence, and presentation.

Do not move business logic into HTTP route handlers or frontend presentation components.

Prefer this direction:

```text
Frontend UI
    -> frontend service/client
    -> backend API
    -> backend service
    -> repository/infrastructure
```

Avoid reverse dependencies that make lower layers import higher-layer UI or route concerns.

---

# CV Processing Architecture

Treat CV processing as a structured pipeline, not as a collection of filename-, candidate-, or resume-specific rules.

Conceptually:

```text
Uploaded document
    ↓
Secure validation
    ↓
Document conversion / native extraction
    ↓
Text normalization
    ↓
Section detection
    ↓
Structured extraction
    ↓
Resume normalization
    ↓
Quality/confidence evaluation
    ↓
Persistence/versioning
    ↓
Matching/search/scoring
    ↓
Optional LLM enrichment
    ↓
API presentation
```

Extraction behavior should be:

- deterministic where practical;
- section-aware;
- evidence-aware;
- confidence-aware;
- reusable across resume layouts;
- resistant to header/footer noise;
- independent of a specific candidate;
- independent of a specific fixture.

Never solve an extraction defect by hardcoding:

- a candidate name;
- a company name;
- an exact resume sentence;
- a specific filename;
- a particular test CV;
- an arbitrary line number;
- one specific section ordering;

unless the value is explicitly part of a documented domain configuration.

Tests may contain literal hardcoded fixtures. Production behavior must not be written specifically to satisfy those literals.

---

# Dynamic Extraction and Matching Rules

Prefer configuration, normalized schemas, registries, reusable evaluators, taxonomies, and evidence models over expanding `if/elif` chains.

When adding a new extraction or matching concept, determine whether it belongs in:

- a schema;
- a section detector;
- an extractor;
- a rule registry;
- a taxonomy;
- configuration;
- a scorer;
- a normalizer;
- an evaluator;
- an evidence structure.

Do not encode domain behavior in presentation strings and then parse those strings downstream.

Prefer:

```text
structured signal
    -> evaluation
    -> presentation
```

over:

```text
formatted text
    -> string parsing
    -> inferred signal
```

---

# Deterministic Logic vs LLM Logic

The deterministic pipeline is the authoritative base path.

LLM functionality is an optional enrichment layer.

Do not make essential CV extraction or core scoring depend entirely on Ollama when a deterministic implementation exists.

Expected principle:

```text
deterministic extraction/evaluation
        ↓
structured result
        ↓
optional LLM enrichment/explanation
```

LLM output must not silently replace stronger deterministic evidence without an explicit design decision.

When LLM functionality is disabled or unavailable, deterministic functionality should degrade gracefully according to existing contracts.

---

# Persistence Rules

## PostgreSQL / pgvector

PostgreSQL is writable application storage.

Use existing repository/database abstractions.

Schema changes must have explicit migrations.

When changing persistence contracts:

- check repository code;
- check migrations;
- check schema-drift verification;
- check tests;
- check backward compatibility.

## MSSQL

MSSQL is an enterprise source and is strictly **READ-ONLY**.

Never:

- INSERT into MSSQL;
- UPDATE MSSQL;
- DELETE from MSSQL;
- ALTER MSSQL;
- CREATE/DROP MSSQL application objects;
- run migrations against MSSQL.

Application synchronization flows pull required data from MSSQL into PostgreSQL.

## Redis

Redis is used for:

- RQ;
- processing records;
- distributed locks;
- caching.

Do not treat arbitrary Redis keys as permanent application truth when a canonical persistent record exists elsewhere.

Preserve key/version conventions used by the existing implementation.

---

# Background Processing

CV uploads use asynchronous processing.

Conceptual flow:

```text
upload
  -> validate document
  -> resolve canonical CV identity
  -> atomically persist source
  -> persist processing record
  -> enqueue job ID
  -> RQ worker reloads source
  -> worker revalidates / hash-checks source
  -> acquire distributed execution controls
  -> process
  -> persist result/state
```

RQ payloads should remain small.

Do not serialize entire CVs or large processing contexts into queue payloads when the worker can resolve them from canonical storage.

Canonical processing states include:

```text
QUEUED
PROCESSING
RETRYING
COMPLETED
FAILED
UNKNOWN
```

Do not confuse processing states with result outcomes such as:

```text
NEW_CV
REPROCESSED
CACHE_HIT
```

Preserve compatibility adapters for legacy polling/status behavior unless intentionally changing the API contract.

---

# Identity and Idempotency

Candidate/CV processing uses canonical identity and version-aware behavior.

Do not fall back to unsafe filename-only identity when canonical identity is available.

Preserve:

- canonical CV identity;
- content/version identity;
- collision protection;
- distributed locking;
- idempotent duplicate processing behavior;
- compatibility aliases only when unambiguous.

A filename is not guaranteed to identify a unique candidate.

---

# Cache and Versioning Rules

Treat semantic changes as potential cache-invalidating changes.

Audit versioning whenever modifying:

- document parsing;
- extraction;
- normalized schemas;
- prompts;
- LLM models;
- embedding models;
- vacancy normalization;
- matching;
- scoring;
- retrieval behavior.

Never return cached results produced under incompatible semantics simply because the input identifier is unchanged.

When changing behavior, explicitly determine:

1. whether existing cache entries remain valid;
2. whether a version must be bumped;
3. whether stored embeddings/results must be regenerated;
4. whether compatibility handling is needed.

---

# API Compatibility

Before changing a backend API:

1. locate the route;
2. locate request/response schemas;
3. search frontend usages;
4. search tests;
5. search compatibility aliases;
6. inspect persisted contracts if relevant.

Preserve existing API paths and successful response fields unless the task explicitly requires a breaking change.

Prefer additive changes.

If a breaking change is unavoidable:

- identify all consumers;
- update them together;
- document the contract change;
- update tests.

---

# Type and Schema Alignment

Backend Pydantic schemas and frontend TypeScript contracts represent the same product concepts.

When a backend response changes:

- inspect corresponding frontend types;
- inspect API transformation/enrichment code;
- inspect consuming components;
- update all affected layers together.

Do not add UI fallbacks that hide a broken backend contract when the correct solution is to update the shared contract.

Do not infer structured backend values by parsing human-readable strings if a typed field can be provided instead.

---

# Compatibility Requirements

The project intentionally preserves compatibility in several areas.

Do not remove compatibility behavior casually.

Examples may include:

- existing API paths;
- legacy upload/status aliases;
- legacy successful response fields;
- normalized additions layered onto existing contracts;
- `document_parser.py` as an extraction compatibility facade;
- canonical job-state adapters;
- unambiguous filename aliases;
- existing error `detail` compatibility alongside structured errors.

When modifying compatibility code, search for both current and legacy consumers.

---

# Security and PII

Resume data contains personally identifiable information.

Treat candidate data as sensitive.

Do not:

- commit real resumes or candidate PII unless they are intentional sanitized test fixtures;
- print full CV content in debug output;
- expose raw internal data through new public endpoints;
- weaken access controls for convenience;
- place secrets in frontend code.

When adding tests, prefer synthetic or properly sanitized data.

---

# Coding Conventions

## General

- Follow existing naming and module conventions.
- Prefer small focused functions.
- Keep responsibilities clear.
- Avoid unnecessary abstraction.
- Avoid unnecessary duplication.
- Use dependency injection where the existing architecture uses it.
- Prefer explicit typed structures over loosely shaped dictionaries for stable domain contracts.
- Keep business logic out of transport/presentation layers.
- Comments should explain intent or non-obvious constraints, not restate the code.
- Remove debug logging before completion unless it is intentionally operational logging.

## Backend

Backend Python targets Python 3.12+.

Use existing Ruff configuration and the `uv` workflow.

## Frontend

Preserve TypeScript type safety, Expo Router conventions, reusable components/hooks, and service-layer API access.

Detailed frontend rules live in `frontend/AGENTS.md`.

---

# Reuse First

Before creating anything new, search for an existing:

- service;
- repository;
- schema;
- normalizer;
- extractor;
- scorer;
- evaluator;
- API helper;
- React component;
- hook;
- utility;
- configuration setting;
- test fixture.

Extend the existing abstraction when that preserves cohesion.

Do not force unrelated responsibilities into an existing class merely to avoid adding a new module.

---

# Documentation

Update documentation when a task changes:

- architecture;
- configuration;
- public APIs;
- setup steps;
- deployment;
- migrations;
- operational procedures;
- compatibility behavior.

Do not update documentation for behavior that was not actually implemented.

---

# Tests

Tests are evidence of intended behavior, but read each test literally.

Many project tests are concrete regression cases rather than generic templates.

Do not assume a hardcoded fixture implies production logic should be hardcoded in the same way.

When fixing a failing case:

1. understand the specific assertion;
2. identify the production defect it exposes;
3. fix the generalized behavior;
4. verify related cases for regressions.

Avoid implementing candidate-specific branches solely to make one fixture pass.

---

# Execution Authorization

Do **not** run any of the following unless the user explicitly authorizes execution:

- test suites;
- linters;
- builds;
- development servers;
- workers;
- migrations;
- Docker builds;
- Docker Compose services;
- external-service integration tests;
- live Ollama tests.

You may inspect source/configuration and state which verification commands should be run.

When execution is authorized, run the narrowest useful verification first, then broaden only as needed.

Never claim tests passed if they were not executed.

---

# Root-Level Setup and Commands

Backend setup:

```bash
cd backend
uv sync --frozen
```

Frontend setup:

```bash
cd frontend
npm install
```

Infrastructure:

```bash
docker compose up -d pgvector redis
```

Migrations:

```bash
docker compose --profile tools run --rm migrate-postgres
```

Application services:

```bash
docker compose up -d api worker
```

Module-specific run/test/lint commands are defined in the nested `AGENTS.md` files.

---

# Migration Rules

For PostgreSQL schema changes:

1. add an explicit forward migration;
2. add a rollback/down migration when repository convention requires it;
3. update models/repositories;
4. update schema-drift expectations;
5. update tests;
6. consider existing production data.

Do not modify an old applied migration to represent a new production change.

Create a new migration.

Never create an MSSQL migration.

---

# Dependency Changes

Before adding a dependency:

- confirm the capability does not already exist;
- consider maintenance and runtime cost;
- consider Docker image impact;
- consider Apple Silicon/local resource impact;
- use the appropriate package manager.

Backend dependency changes belong in `pyproject.toml` / `uv.lock`.

Frontend dependency changes belong in the package manifest/lockfile.

Do not manually edit lockfiles unless required by the package-management workflow.

---

# Expected Agent Workflow

For a substantial implementation task:

```text
1. Understand request
2. Read applicable AGENTS.md files
3. Inspect current architecture
4. Search references/usages
5. Identify root cause
6. Identify affected contracts
7. Design smallest generalized fix
8. Implement
9. Update tests
10. Run authorized verification
11. Review diff for unrelated changes
12. Update documentation/workstatus if needed
13. Report exact outcome and remaining risk
```

Do not jump directly from a reported symptom to code changes without locating the responsible layer.

---

# Expected Task Report

For substantial code changes, final reporting should cover:

1. Root cause
2. What changed
3. Files changed
4. Compatibility impact
5. Verification performed
6. Verification not performed
7. Remaining limitations or risks

Do not force this format for trivial tasks where a short response is clearer.

---

# Definition of Done

A task is complete only when the requested behavior is implemented consistently across the affected architecture.

Before considering a change complete, confirm as applicable:

- the root cause was addressed;
- no candidate/test-specific hack was introduced;
- existing abstractions were reused;
- API contracts remain compatible or were intentionally updated;
- backend/frontend types remain aligned;
- database changes have migrations;
- MSSQL remains read-only;
- cache/version semantics remain valid;
- queue behavior remains idempotent;
- Ollama behavior remains centralized;
- tests were updated where behavior changed;
- authorized verification was actually run;
- no unrelated files were modified;
- documentation reflects meaningful operational changes.

Correctness, maintainability, compatibility, and evidence are more important than making a single test case pass.