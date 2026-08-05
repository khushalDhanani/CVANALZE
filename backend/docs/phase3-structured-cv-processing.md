# Phase 3 Structured CV Processing and Database-Driven Taxonomy

## Scope and Architecture Impact

Phase 3 introduces a robust, typed, and normalized structure for all extracted CV data, ensuring downstream matching and scoring engines operate on deterministic data types rather than loosely structured JSON. In addition, this phase decouples all business-specific taxonomy terms and compatibility mappings from static JSON files, migrating them to the database for dynamic, tenant-safe updates.

## 1. Backward-Compatible Document Parser Facade

The `app.services.document_parser` module acts as a strict compatibility facade. It hides the complexity of the underlying pipeline (document conversion, field extraction, quality metrics, and text normalization) from legacy endpoints, ensuring no breaking changes to API contracts.

Legacy consumers can continue using existing imports (e.g., `MarkdownGenerator`, `ResumeJsonExtractor`, `QualityMetricsCalculator`, and `TextSanitizer`) while benefiting from the updated internal validation and caching improvements.

## 2. Normalized Data Structures (`NormalizedResume`)

To solve issues with arbitrary string formatting returned by the LLM extraction stage, Phase 3 introduces the `NormalizedResume` Pydantic schema. 

Every extracted data point (contact information, skills, education, employment) now retains:
- **`raw_value`**: The exact substring text found in the original document.
- **`normalized_value`**: The strongly-typed, cleaned equivalent (e.g., lowercase email, standardized degree).
- **`confidence`**: A floating-point confidence score (0.0 - 1.0) assessing the extraction quality.
- **`evidence`**: A list of original document text blocks that substantiate the extraction.

This structure guarantees that the original intent and format of the CV are always preserved and auditable, even after aggressive normalization.

## 3. Deterministic Experience Calculation

To resolve "Experience: N/A" errors and calculation bugs, a dedicated `DateIntervalParser` and `ExperienceCalculator` were implemented. 

### Core Invariant
**Extracted document dates are strictly authoritative.** 

The experience calculator evaluates raw date ranges, resolves overlapping intervals, and applies duration heuristics deterministically. It explicitly falls back to LLM-derived experience values or stated total experience *only* if the employment dates are completely missing or mathematically unparseable.

## 4. Context Schema Reuse (`MatchService`)

To eliminate redundant extraction and repetitive data modeling during batch matching operations, Phase 3 introduces `CandidateAnalysisContext` and `JobEvaluationContext`.

- **`CandidateAnalysisContext`**: Retains the pre-built `NormalizedResume` and computed deterministic experience.
- **`JobEvaluationContext`**: Retains the pre-filtered vacancy schema and parsed requirements.

The `MatchService` is now context-aware. If an explicit `CandidateAnalysisContext` is supplied, it completely bypasses the document parsing, CV validation, and normalization phases, drastically improving throughput when matching one candidate against hundreds of vacancies.

## 5. Database-Driven Taxonomy (Audit Resolution)

Phase 3 officially deprecates the static `department_domains_seed.json` and `rule_config.json` files from runtime usage, resolving high-priority violations in the Backend Architecture Audit Report.

- **`TaxonomyService`**: Now the single source of truth for the `FamilyCompatibility` mappings, querying the database and maintaining an in-memory cache.
- **Decoupled Rule Configuration**: The `RuleConfigManager` was cleansed of the tightly-coupled `compatibility_map` dictionary, allowing taxonomy administrators to add new job families or domains in the database without requiring a backend code deployment.

## Compatibility and Deprecations

- Existing result records stored as untyped JSON will seamlessly upgrade to `NormalizedResume` shapes upon their next cache miss or reprocessing event.
- Relying on `dyn_res.family_name` or `dyn_res.domain_name` in dynamic taxonomy classification is deprecated. Callers must use the correct `NormalizedClassification` DB fields (e.g., `industry_department`, `industry_domain`, `db_designation_name`).
