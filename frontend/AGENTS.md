# frontend/AGENTS.md

## Scope

This file applies to everything under `frontend/`.

It extends the repository-root `AGENTS.md` with frontend-specific architecture, UX, TypeScript, Expo Router, API integration, testing, and styling rules.

Read the root `AGENTS.md` first.

---

# Frontend Work Logging (`workstats.md`)

All frontend modifications, UI/UX improvements, new components, screens, hooks, types, API client integrations, and styling changes must be logged immediately upon completion into `workstats.md` at the repository root.

Follow the append-only rule: never delete, overwrite, or edit past log entries; add each change as a new sequential entry (`### Entry #XXX`) at the bottom of the file.

---

# Frontend Mission

The frontend is a recruiter-facing interface for:

- candidate CV analysis;
- candidate detail review;
- vacancy review;
- candidate-to-vacancy matching;
- requirement evidence;
- hiring risks;
- analytics;
- batch workflows;
- configuration/admin flows;
- domain/taxonomy exploration;
- related recruiter operations.

The UI should help a recruiter understand important candidate information quickly with minimal scrolling.

---

# Technology

The frontend uses the repository's current Expo/React Native stack, including:

- Expo;
- Expo Router;
- React;
- React Native;
- React Native Web;
- TypeScript;
- NativeWind/Tailwind-style utilities.

Use versions already pinned in `package.json`.

Do not upgrade Expo, React, React Native, or routing dependencies as part of unrelated work.

When using version-sensitive Expo APIs, verify compatibility with the currently installed Expo version rather than relying on generic examples from older SDKs.

---

# Frontend Layout

Use the existing source boundaries:

```text
frontend/
├── AGENTS.md
├── package.json
└── src/
    ├── __tests__/
    ├── app/
    ├── components/
    ├── constants/
    ├── hooks/
    ├── services/
    ├── types/
    ├── utils/
    └── global.css
```

Do not create parallel `pages/`, `api/`, or `lib/` trees unless the architecture is intentionally being changed.

---

# `src/app/`

`src/app/` owns route-level screens and Expo Router composition.

Appropriate responsibilities:

- route parameters;
- page-level loading;
- page-level error/empty states;
- composing components;
- wiring hooks/services into the route;
- navigation behavior.

Avoid turning route files into large monolithic feature implementations.

Extract reusable or complex UI into `src/components/`.

Move reusable stateful logic into `src/hooks/`.

Move backend communication into `src/services/`.

---

# `src/components/`

Owns reusable UI components.

Components should:

- accept typed props;
- avoid direct knowledge of unrelated routes;
- avoid repeated API fetching if the parent/service already owns the data;
- expose clear loading/empty/error states when applicable;
- remain reusable across candidate/vacancy contexts when the semantics are genuinely shared.

Do not create a second component that is 90% identical to an existing one when the existing component can be extended cleanly.

---

# `src/hooks/`

Owns reusable stateful behavior.

Hooks may encapsulate:

- data-fetching orchestration;
- derived state;
- selection/filter state;
- debouncing;
- pagination state;
- reusable interaction logic.

Do not place large render trees inside hooks.

Avoid duplicating backend state in multiple hooks with conflicting sources of truth.

---

# `src/services/`

Owns backend/API communication.

Use services for:

- HTTP requests;
- endpoint composition;
- request payload normalization;
- response adaptation when needed;
- shared request error behavior.

Do not scatter `fetch()`/HTTP calls across route components if equivalent logic belongs in a service.

Do not hardcode API base URLs in feature components.

Use existing configuration/environment mechanisms.

---

# `src/types/`

Owns shared TypeScript contracts.

Keep frontend types aligned with backend API contracts.

When backend response fields change:

1. update frontend types;
2. update service transformations;
3. update consuming components;
4. update tests.

Avoid `any`.

Prefer explicit optionality:

```ts
field?: string | null
```

when that matches the real backend contract.

Do not hide schema drift using broad index signatures unless genuinely required.

---

# `src/utils/`

Owns reusable pure helpers.

Good utility candidates:

- formatting;
- safe normalization;
- small parsing helpers;
- deterministic UI calculations.

Do not place business-critical candidate matching logic in frontend utilities when the backend owns that domain behavior.

---

# `src/constants/`

Owns shared constants.

Use constants for stable presentation/config values.

Do not use constants as a substitute for dynamic backend-driven configuration when the value belongs to domain policy.

---

# API Contract Rules

The frontend is a consumer of backend contracts.

Do not infer structured values by parsing labels when the backend provides or can provide explicit fields.

Prefer:

```text
backend structured field
    -> TypeScript type
    -> UI presentation
```

over:

```text
backend sentence
    -> regex/string split
    -> inferred UI state
```

When a backend contract is wrong, fix the contract rather than adding layers of frontend guessing.

---

# Candidate Detail UX

Candidate pages should allow a recruiter to answer these quickly:

- Who is the candidate?
- What role/profile do they represent?
- What are their strongest relevant skills?
- How much relevant experience is present?
- What evidence supports the extraction/match?
- What are the important gaps or risks?
- What is the vacancy-match outcome?
- What action should the recruiter take next?

Avoid forcing the recruiter through excessive scrolling to discover essential evaluation information.

Prioritize above-the-fold or early-page visibility for:

- candidate identity;
- concise profile summary;
- key skills;
- experience summary;
- match score/status;
- mandatory requirement failures;
- major hiring risks;
- key evidence.

---

# UI Density

The product should be compact but readable.

Prefer a density closer to modern admin/recruiter tools rather than oversized consumer landing pages.

Avoid:

- excessive vertical padding;
- overly tall cards;
- large headings repeated on every section;
- nested cards inside cards without a reason;
- repeated labels;
- large empty areas;
- oversized buttons for secondary actions.

Use consistent spacing tokens.

When tightening UI, preserve:

- accessibility;
- click/tap targets;
- hierarchy;
- readability;
- responsive behavior.

Do not reduce every spacing value blindly.

---

# Information Hierarchy

Use visual hierarchy to separate:

1. decision-critical information;
2. supporting evidence;
3. detailed/raw extraction data.

Do not give raw debug/extraction payloads equal visual importance to recruiter decisions.

Long evidence lists should support progressive disclosure where appropriate.

---

# Requirement Evidence UI

Requirement-level matching should show structured evidence where available.

Prefer rows/cards containing:

- requirement;
- candidate evidence;
- vacancy/JD evidence;
- assessment state;
- conclusion;
- confidence/failure reason where useful.

Do not fabricate evidence.

Clearly distinguish:

- matched;
- not matched;
- not found;
- not assessable;
- unknown.

Avoid relying only on color to communicate state.

---

# Hiring Risk UI

Hiring risks should reflect backend structured risk objects.

Do not independently recreate risk rules in the frontend.

The UI may:

- group risks;
- prioritize severity;
- collapse low-priority details;
- explain evidence.

But domain policy should remain backend-driven.

---

# Loading States

Every async page/section should have a deliberate loading experience.

Avoid:

- blank screens;
- layout jumps that move major controls excessively;
- stale values displayed as if they were current.

Use existing loading/skeleton/spinner conventions.

Do not invent a second loading system if a shared one already exists.

---

# Empty States

Distinguish legitimate empty data from request failures.

Examples:

- no projects found;
- no education extracted;
- no vacancy selected;
- no matching evidence available;
- no search results.

Do not label an API error as "No data".

---

# Error States

Errors should be understandable and actionable.

Do not show raw backend stack traces or low-level networking details.

Use established service/error helpers.

Preserve useful correlation/request IDs if the API surfaces them and the UI already supports them.

---

# Responsive Behavior

The frontend targets native/mobile and web contexts.

Do not optimize only for one desktop width.

Check:

- narrow mobile widths;
- common tablet widths;
- desktop/web;
- long names;
- long skill labels;
- large evidence lists;
- variable card content.

Avoid fixed widths unless there is a specific layout reason.

---

# Navigation

Preserve Expo Router conventions.

Use route params consistently.

Do not bypass the router with ad-hoc URL manipulation unless existing web-specific architecture requires it.

When renaming/moving a route, search all navigation links and deep-link references.

---

# Styling

Reuse existing NativeWind/Tailwind utilities and shared style patterns.

Avoid:

- repeated inline style objects;
- arbitrary spacing values when existing utilities fit;
- duplicating color/spacing tokens;
- large style rewrites unrelated to the task.

When adding a new repeated visual pattern, consider a reusable component or shared token.

---

# Color and Status

Status colors must not be the sole method of conveying meaning.

Pair color with:

- text;
- icon;
- label;
- shape;

as appropriate.

Respect existing theme behavior.

Do not introduce new semantic colors casually when an established status palette exists.

---

# Accessibility

Preserve accessibility.

For interactive controls:

- provide meaningful labels;
- retain appropriate tap/click area;
- use accessible roles where relevant;
- do not create tiny icon-only actions without context;
- preserve keyboard/web usability when applicable.

Do not trade accessibility for compactness.

---

# Performance

Avoid unnecessary re-renders and expensive calculations in render paths.

But do not add `useMemo`/`useCallback` everywhere without evidence.

Prioritize:

- stable keys;
- efficient long lists;
- avoiding duplicate API calls;
- avoiding repeated normalization;
- sensible component boundaries.

For large candidate/evidence lists, use existing list/virtualization patterns where appropriate.

---

# Data Ownership

Avoid multiple sources of truth.

If API data is loaded at the route level and passed down, child components should not independently refetch the same resource unless intentionally designed.

Derived presentation state should not overwrite the raw canonical API object.

---

# Frontend vs Backend Responsibility

The backend should own:

- CV extraction;
- normalization;
- semantic matching;
- scoring;
- hiring-risk policy;
- requirement evaluation;
- domain decisions.

The frontend should own:

- presentation;
- interaction;
- filtering/sorting for display when appropriate;
- route/navigation state;
- local form state;
- visual grouping.

Do not move business-critical decisions to the frontend just because they are easier to display there.

---

# TypeScript Rules

Prefer:

- typed function parameters;
- typed component props;
- typed service responses;
- discriminated unions for meaningful state variations when helpful.

Avoid:

- `any`;
- unsafe casts;
- `as unknown as X`;
- non-null assertions used to silence real uncertainty.

If a cast is necessary, document why.

---

# React Rules

Use functional components and hooks consistent with the codebase.

Avoid:

- state that can be derived from props;
- effects used purely for synchronous derivation;
- effect dependency suppression without understanding the cause;
- duplicating server data into local state without a clear editing workflow.

Keep components focused.

---

# Expo Version Rules

Use APIs supported by the repository's installed Expo SDK.

Do not copy code from examples targeting older/newer Expo SDKs without checking compatibility.

Pay special attention to version-sensitive areas such as:

- file system;
- routing;
- platform APIs;
- permissions;
- fonts/assets;
- native modules.

---

# Environment and API Base URL

Use existing environment/configuration mechanisms.

Do not hardcode:

```text
http://localhost:8000
```

inside feature components or reusable services unless that is explicitly the project's existing dev configuration mechanism.

Support the repository's web/native networking expectations.

---

# Testing

Frontend tests live under the existing test structure.

Read tests literally.

Do not assume a hardcoded test is intended as a reusable parameterized template.

When fixing UI behavior:

- update the generalized component/logic;
- preserve the regression scenario;
- add edge cases where useful.

Avoid tests that depend on:

- implementation-private details;
- arbitrary timing;
- unstable generated text;
- meaningless snapshots.

---

# Commands

Install:

```bash
npm install
```

Start Expo:

```bash
npm start
```

Platform commands:

```bash
npm run android
npm run ios
npm run web
```

Lint:

```bash
npm run lint
```

Do not invent scripts that are not present in `package.json`.

If a test command is needed, inspect `package.json` and the current test setup first.

---

# Execution Authorization

Do not run:

- lint;
- tests;
- builds;
- Expo development servers;
- native builds;

without explicit user authorization.

You may inspect source and recommend commands.

Never claim a frontend build/test/lint passed unless it was actually executed.

---

# Dependency Changes

Before installing a dependency:

- confirm the capability is not already present;
- verify compatibility with current Expo/React Native versions;
- consider web + native behavior;
- consider bundle size;
- consider maintenance quality.

Use the existing package manager and lockfile.

Do not upgrade the framework stack as collateral work.

---

# Refactoring

A frontend refactor is justified when it:

- removes duplicated screens/components;
- reduces excessive page complexity;
- centralizes API calls;
- strengthens type safety;
- improves recruiter scanability;
- reduces unnecessary scrolling;
- improves responsive behavior;
- preserves functionality.

Do not perform a full visual rewrite for a localized bug.

---

# Compactness Review Checklist

For pages/components changed as part of density work, inspect:

- outer page padding;
- section margins;
- card padding;
- header height;
- row height;
- table cell padding;
- button size;
- icon size;
- typography scale;
- duplicated section titles;
- empty wrappers;
- nested cards;
- repeated metadata;
- mobile wrapping.

Prioritize the largest space savings with the lowest usability risk.

---

# Candidate Page Review Checklist

For `candidates/[id]`-style pages, verify:

- candidate name is prominent and correct;
- title/summary does not replace the actual name;
- contact data is clearly separated from employers/projects;
- skills are concise and prioritized;
- experience timeline is understandable;
- project experience is not presented as employment unless classified that way;
- HTML entities are decoded;
- requirement evidence is scannable;
- major mismatch/risk signals appear early;
- raw details do not dominate the top of the page.

---

# Frontend Definition of Done

Before considering frontend work complete, confirm as applicable:

- correct route/component/service/type layer was changed;
- API calls are centralized appropriately;
- types match backend contracts;
- no business-critical backend policy was duplicated in UI;
- page remains responsive;
- information hierarchy is improved or preserved;
- compactness did not harm usability;
- loading, empty, and error states still work;
- accessibility is preserved;
- no unrelated visual changes were introduced;
- authorized lint/tests/build were actually run;
- no verification is claimed unless executed;
- changes were logged immediately to root `workstats.md` (append-only).

The recruiter should be able to understand the important candidate/vacancy outcome faster after the change, not slower.