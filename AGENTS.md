# AGENTS.md

## Before Starting

* Read `AGENTS.md`.
* Read `workstatus.md` if it exists; otherwise create it.
* Update `workstatus.md` at the end of every task with work completed, files changed, pending work, and important decisions.

## Scope

* Modify only files related to the requested task.
* Do not modify unrelated files.
* Do not refactor or reformat unrelated code.
* Preserve existing project conventions.

## Code Style

* Apply these rules to all code (C#, SQL, HTML, CSS, JavaScript, TypeScript, Razor, JSON, XML, YAML, etc.).
* Keep every line under 200 characters where practical.
* Do not wrap lines unless required by syntax or readability.
* Keep formatting consistent with the existing project.

## Reuse First

* Reuse existing code, helpers, services, repositories, components, and utilities before creating new ones.
* Reuse existing CSS classes whenever possible.
* Create new CSS only when necessary, using generic, reusable class names and placing them in the appropriate common or feature stylesheet.

## API Changes

* Check existing usages before modifying an API.
* Do not introduce breaking changes.
* Preserve existing request and response contracts unless explicitly instructed to change them.

## HTML & CSS

* Preserve existing HTML formatting unless a change is required.
* Avoid unnecessary whitespace, formatting, or attribute-order changes.
* Keep Git diffs focused on functional changes only.

## Build & Run

* Do not build, run, restore, test, publish, or execute migrations unless explicitly requested.

## General

* Follow the existing codebase architecture, design patterns, naming conventions, and coding style.
* Follow SOLID principles and Clean Architecture where applicable without conflicting with the existing codebase.
* Keep solutions simple, maintainable, reusable, and production-ready.
* Make the smallest safe change that satisfies the request.
* Ask for clarification only when required to avoid incorrect implementation.

## Ollama Backend Architecture & Standardization Policy

Before implementing any feature that interacts with Ollama:
1. Audit the existing backend to identify every Ollama integration.
2. List every affected file before making changes.
3. Reuse existing services, repositories, schemas, configuration, caching, retry logic, and HTTP clients.
4. Never create duplicate Ollama clients, endpoint wrappers, configuration, or business logic.
5. Normalize every Ollama request through the existing centralized services.
6. Preserve backward compatibility and existing API contracts.
7. Follow the project's architecture, naming conventions, dependency injection, and coding style.
8. Refactor when necessary to keep Ollama integration centralized and maintainable.
9. Update tests whenever behavior changes.
10. After implementation, verify that every Ollama endpoint behaves consistently across the entire backend.

### Standardization Rules
- **One configuration source**: `app.core.config.settings`
- **One HTTP client**: Shared client instance with connection pooling and configurable timeout.
- **One retry strategy**: Uniform retry loop using `OLLAMA_MAX_RETRIES` and exponential backoff.
- **One timeout strategy**: `OLLAMA_REQUEST_TIMEOUT` across all LLM operations.
- **One caching strategy**: `LLMCacheRepository` for LLM generation; `EmbeddingService` cache manager for vectors.
- **One error handling strategy**: Standardized connection error catching, logging, and fallback mechanisms.
- **One request/response format**: Standardized payload builder and Pydantic schema validation.
- **One logging strategy**: Unified `logger` format for HIT/MISS, duration, and error traces.
- **One model selection strategy**: Centralized model defaults with runtime override support.
- **One streaming/non-streaming implementation**: Centralized non-streaming JSON generation wrapper.
- **One embedding implementation**: Centralized `EmbeddingService` handling all `/api/embed` interactions.
- **One generation implementation**: Centralized `OllamaLLMService` handling all `/api/generate` and `/api/tags` interactions.

### Required Output Order for Every Task
1. Architecture impact analysis
2. Files to modify
3. Implementation plan
4. Code changes
5. Verification checklist
6. Any refactoring performed

