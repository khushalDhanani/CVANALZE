# Resume Section Integrity Design

## Purpose

Prevent Projects and Education data from being invented, cross-mapped, duplicated, or propagated into matching and recruiter recommendations across heterogeneous CV formats. The deterministic extraction pipeline remains authoritative; optional LLM behavior cannot create or promote these records.

## Confirmed Failure Chain

The current section-heading recognizer does not cover common variants such as `Educational Background`. When no canonical education section is produced, education extraction runs against the entire document. Its generic heading, degree, and date rules then turn profile, employment, skills, interests, and declaration content into education records.

When no Projects section is present, project extraction scans the entire document and treats unrecognized Markdown subheadings as projects. Those false projects are normalized, stored, exposed by the candidate API, merged again by the frontend, counted as project experience, and used by recommendation generation.

Degree normalization independently contains an ambiguous case-insensitive abbreviation pattern that matches the month `March` as `M.Arch`. The frontend then merges raw and normalized education sources by display strings; changed normalized values fail deduplication and create extra cards.

## Design Principles

- Classification precedes field extraction.
- Unknown content remains unknown; absence of a section is not permission to scan the entire CV with a section-specific extractor.
- Every accepted record has source-section provenance and sufficient deterministic evidence.
- Rejected records are observable through bounded reason codes, not exposed as candidate facts.
- Normalization may standardize validated evidence but may not infer a different semantic type.
- One canonical collection feeds storage, API, UI, vectors, matching, and recommendations.
- Existing successful API fields remain compatible; integrity additions are additive.
- Validation cost is linear in document lines and bounded for bulk processing.

## Canonical Section Model

Add a centralized section classifier used by resume extraction. It will normalize Markdown markers, punctuation, whitespace, ampersands, and case before matching aliases. It will return ordered section blocks containing:

- canonical section type;
- original heading;
- content lines;
- start and end line indexes;
- classification confidence and deterministic reason.

Canonical types include `general`, `contact`, `summary`, `experience`, `education`, `projects`, `skills`, `certifications`, `languages`, `interests`, `safety`, `competencies`, `declaration`, and `unknown`. Alias configuration covers generic heading families rather than candidate-specific strings. Unknown headings delimit blocks but never become projects or institutions.

The existing resume-quality section patterns will use the same heading registry so quality measurement and extraction cannot disagree about whether a section exists.

## Education Extraction and Validation

Education extraction receives only education blocks. It supports:

1. Markdown or pipe-delimited tables with header-to-column mapping for course/degree, institution/board/university, year/date, and grade/percentage.
2. Tabular text where columns are separated by repeated whitespace or tabs.
3. Inline records containing a recognized qualification plus supporting institution, date, or grade evidence.
4. Multiline records where degree, institution, dates, and grade are adjacent within the same education block.

An education record is accepted only when it contains a qualification signal or a recognized education context plus at least one supporting field. Section headings, contact data, employment date ranges, job titles, declarations, and unrelated headings are rejected. Table separator and header rows are never data records.

Records are deduplicated by a canonical fingerprint built from normalized degree, institution, completion year, and grade. Missing fields are merged only when populated fields do not conflict.

Degree abbreviation matching will distinguish degree tokens from ordinary words and month names. A raw value that lacks a validated qualification signal is never passed to degree canonicalization. Normalized confidence reflects the validation result instead of assigning high confidence merely because a string is present.

## Project Extraction and Validation

Projects are extracted from a canonical Projects block. Embedded projects outside that block require an explicit marker such as `Project Title`, `Project Name`, `Project Highlights`, or a project-labeled employment subsection.

An accepted project requires a title plus at least one substantive evidence channel: description, responsibility/bullet, technologies, outcome, or explicit project marker. The validator rejects contact headings, candidate names, section labels, job titles paired with employer/date ranges, education rows, declarations, interests, and safety/skills headings.

Projects are deduplicated using normalized title plus evidence fingerprint. Employment responsibilities remain employment evidence unless explicitly scoped as a project. No general full-document subheading fallback remains.

## Integrity Result and Diagnostics

Extraction will produce canonical accepted `education` and `projects` collections and an additive integrity summary with:

- accepted counts by field;
- rejected counts by field and stable reason code;
- duplicate counts;
- whether a canonical source section was found;
- extraction-policy version.

Reason codes include `WRONG_SECTION`, `SECTION_HEADING_ONLY`, `INSUFFICIENT_EVIDENCE`, `EMPLOYMENT_SHAPED`, `CONTACT_SHAPED`, `TABLE_HEADER`, `DUPLICATE`, and `MALFORMED_VALUE`. Logs contain candidate/run identifiers, counts, durations, and reason codes only. Raw CV text, contact data, and rejected PII are not logged.

Unexpected, null, scalar, or malformed collections normalize to empty lists and generate diagnostics rather than exceptions. Per-document validation remains O(lines + records), with configured caps on section count, record count, field length, and evidence items.

## Normalization, Storage, and API

`ResumeNormalizer` consumes only accepted raw records. Normalized Education and Project structures preserve raw evidence and source-section metadata. Normalization cannot add a record absent from the accepted collection.

The stored result keeps `resume_json.education` and `resume_json.projects` as the backward-compatible authoritative raw collections. `normalized_resume` contains their normalized projections. An additive `extraction_integrity` object records diagnostics and the policy version.

The candidate API continues returning existing fields. It also exposes authoritative typed collections through the existing resume/normalized envelopes and the integrity summary. It does not independently recompute or merge rejected legacy data.

The extraction semantics/version identity is bumped so incompatible cached results are not silently reused. A resumable administrative reprocessing command supports dry-run reporting, explicit batch size, continuation cursor, bounded failures, and idempotent reanalysis. Merely deploying the code does not automatically rewrite all stored candidates.

## Frontend Mapping and Rendering

The candidate-detail view model selects one authoritative source per field:

- normalized validated records when integrity/version metadata confirms the new contract;
- otherwise validated raw records;
- legacy merge behavior only for older payloads, with defensive semantic filtering and canonical deduplication.

The UI will not union raw and normalized collections from the same extraction generation. Education mapping supports typed normalized fields and arrays without converting headings into cards. Projects render descriptions, technologies, and bullet points. Compact mode limits both projects and Interview Focus; the expansion button appears only when hidden content exists.

Counts reflect the rendered validated collection. Empty validated projects render `Projects (0)` and `No projects were identified.` Integrity diagnostics remain operational data and are not shown as candidate facts.

## Recommendations and Interview Focus

Project strengths and counts consume the validated canonical projects collection. Empty projects produce no project-experience strength. Equivalent missing requirements are deduplicated by normalized semantic key.

Interview Focus preserves known acronyms such as SAP, DCS, SCADA, HAZOP, and P&ID. Department-fit prompts describe ambiguity when no authoritative main department exists; talent-pool assignment is withheld when the same result requires manual department review.

Education-specific focus is generated only when a vacancy education requirement exists or the education evidence is incomplete/conflicting. It cites validated degree evidence rather than raw section text.

## Compatibility and Failure Handling

- No API route or existing successful response field is removed.
- Legacy stored results remain readable through a defensive compatibility adapter.
- New processing writes only the validated contract.
- Invalid records fail closed: they are omitted from candidate facts but counted in diagnostics.
- A document with no Projects or Education section completes successfully with empty collections.
- A malformed record cannot abort processing of otherwise valid records.
- Optional LLM failure does not alter deterministic Projects or Education.

## Regression Strategy

Backend tests use synthetic, PII-free fixtures covering:

- the reported chemical-engineer layout with an education Markdown table and no Projects section;
- standard Markdown headings;
- uppercase and mixed-case aliases;
- tabular and multiline education;
- projects before or after employment;
- explicit embedded project markers;
- employment-only CVs;
- CVs with no education or projects;
- long documents with repeated headers/footers;
- null, scalar, partial, malformed, and oversized values;
- duplicate raw records;
- the `March` versus `M.Arch` normalization collision;
- contact, declaration, interests, safety, and skills cross-mapping attempts.

Contract tests verify stored/API counts and provenance. Recommendation tests verify that rejected projects do not create strengths and ambiguous departments do not create definitive assignments. Frontend tests verify authoritative-source selection, legacy filtering, deduplication, counts, bullet rendering inputs, and expansion-state calculations.

Targeted unit and integration tests run before broader backend and frontend type/runtime checks. The full release gate is not required unless separately requested because this change does not modify release-gate registration.

## Operational Acceptance Criteria

- The reported CV yields exactly three education records and zero projects.
- No candidate/contact/employment/section-heading value appears under Projects or Education.
- `March` never normalizes to `M.Arch`; valid M.Arch variants still normalize correctly.
- Raw and normalized projections represent the same accepted record set.
- UI counts equal rendered canonical records without duplicates.
- Recommendation project counts equal validated project counts.
- All rejection paths emit bounded aggregate diagnostics without PII.
- Processing cost grows linearly and malformed documents fail per record rather than per batch.
