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
