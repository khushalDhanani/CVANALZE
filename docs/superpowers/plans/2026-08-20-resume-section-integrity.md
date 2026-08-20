# Resume Section Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for every behavior change and superpowers:verification-before-completion before reporting completion. The tasks are tightly coupled through the extraction contract and are executed sequentially in the current shared workspace.

**Goal:** Make Projects and Education extraction deterministic, provenance-aware, non-fabricating, and consistent through normalization, storage/API consumption, frontend rendering, and recommendation generation.

**Architecture:** Introduce a canonical section model and record-integrity helpers beside the existing resume extractor. Section-specific extractors consume only classified blocks and return validated records plus bounded diagnostics. Downstream layers consume one authoritative record set and fail closed for legacy malformed payloads.

**Tech Stack:** Python 3.12, FastAPI/Pydantic, pytest, TypeScript, Expo/React Native, repository runtime TypeScript tests.

**Spec:** `docs/superpowers/specs/2026-08-20-resume-section-integrity-design.md`

## Global Constraints

- No candidate-specific strings, filenames, employers, or literal resume sentences in production logic.
- Deterministic extraction remains authoritative; LLM behavior cannot create Projects or Education records.
- Existing API routes and successful fields remain compatible; new integrity metadata is additive.
- MSSQL remains read-only and no database migration is required for JSON result additions.
- Logs contain identifiers, counts, durations, and stable reason codes only—never CV text or rejected PII.
- Runtime work is linear in lines plus extracted records and uses bounded field/record sizes.
- The shared checkout contains unrelated PostgreSQL-capacity edits; do not modify or commit them.
- Do not create Git commits unless the user separately requests commits.

---

### Task 1: Canonical section classification and validated extraction

**Files:**
- Create: `backend/app/services/resume_sections.py`
- Modify: `backend/app/services/resume_field_extractor.py`
- Modify: `backend/app/services/resume_quality.py`
- Test: `backend/tests/unit/services/test_resume_section_integrity.py`
- Test: `backend/tests/unit/services/test_resume_field_extractor.py`

**Interfaces:**
- Produces `SectionKind`, `ResumeSection`, `SectionDetectionResult`, and `ResumeSectionDetector.detect(lines)`.
- Produces accepted `resume_json.education`, accepted `resume_json.projects`, and additive `extraction_integrity`.
- Existing `ResumeFieldExtractor._split_sections()` remains as a compatibility adapter over the new detector.

- [ ] **Step 1: Write failing multi-format extraction tests**

```python
def test_education_table_without_projects_does_not_cross_map_sections():
    result = ResumeFieldExtractor.extract(CHEMICAL_ENGINEER_MARKDOWN)
    assert result["projects"] == []
    assert result["education"] == [
        {"degree": "B.E. Chemical", "institution": "GTU", "dates": "2019", "grade": "7.59 CGPA", "source_section": "education"},
        {"degree": "H.S.C", "institution": "GHSEB", "dates": "2015", "grade": "63%", "source_section": "education"},
        {"degree": "S.S.C", "institution": "GSEB", "dates": "2013", "grade": "67.5%", "source_section": "education"},
    ]

def test_explicit_projects_are_retained_but_employment_headings_are_not_projects():
    result = ResumeFieldExtractor.extract(MIXED_PROJECT_AND_EMPLOYMENT_MARKDOWN)
    assert [item["name"] for item in result["projects"]] == ["Inventory Forecasting"]

def test_missing_and_malformed_sections_fail_closed_with_diagnostics():
    result = ResumeFieldExtractor.extract(MALFORMED_SECTION_MARKDOWN)
    assert result["education"] == []
    assert result["projects"] == []
    assert result["extraction_integrity"]["rejected_counts"]
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd backend && uv run pytest tests/unit/services/test_resume_section_integrity.py -q`

Expected: failures showing missing canonical classifier, cross-mapped records, or missing diagnostics.

- [ ] **Step 3: Implement canonical section detection**

```python
class SectionKind(StrEnum):
    GENERAL = "general"
    CONTACT = "contact"
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    PROJECTS = "projects"
    SKILLS = "skills"
    CERTIFICATIONS = "certifications"
    LANGUAGES = "languages"
    INTERESTS = "interests"
    SAFETY = "safety"
    COMPETENCIES = "competencies"
    DECLARATION = "declaration"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class ResumeSection:
    kind: SectionKind
    heading: str | None
    lines: tuple[str, ...]
    start_line: int
    end_line: int
    confidence: float
    reason: str
```

Normalize heading markers/punctuation, map alias families, preserve unknown blocks, and bound line/section sizes.

- [ ] **Step 4: Implement section-scoped Education and Projects extraction**

Education parsing handles Markdown tables, delimited rows, and multiline records. Project fallback requires explicit project markers. Add validators and stable rejection reasons:

```python
REJECTION_REASONS = {
    "WRONG_SECTION", "SECTION_HEADING_ONLY", "INSUFFICIENT_EVIDENCE",
    "EMPLOYMENT_SHAPED", "CONTACT_SHAPED", "TABLE_HEADER",
    "DUPLICATE", "MALFORMED_VALUE",
}
```

Remove full-document Education fallback and arbitrary-subheading Project fallback. Deduplicate accepted records by canonical evidence fingerprints.

- [ ] **Step 5: Reuse the canonical detector in resume quality and compatibility section splitting**

Ensure quality scoring and extraction resolve the same aliases. Preserve the existing `_split_sections()` dictionary contract for callers/tests.

- [ ] **Step 6: Run focused extraction tests and Ruff**

Run:

```bash
cd backend
uv run pytest tests/unit/services/test_resume_section_integrity.py tests/unit/services/test_resume_field_extractor.py -q
uv run ruff check app/services/resume_sections.py app/services/resume_field_extractor.py app/services/resume_quality.py tests/unit/services/test_resume_section_integrity.py
```

Expected: all focused tests pass; Ruff exits zero.

---

### Task 2: Normalization, schema, provenance, and cache version integrity

**Files:**
- Modify: `backend/app/services/resume_normalizer.py`
- Modify: `backend/app/schemas/normalized_resume.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/schemas/cv.py`
- Test: `backend/tests/unit/services/test_resume_section_integrity.py`
- Test: `backend/tests/unit/schemas/test_api_contracts.py`

**Interfaces:**
- Consumes only Task 1 accepted records.
- Adds typed optional source-section provenance and additive `extraction_integrity` API metadata.
- Uses parser version `1.1.0` and extraction schema version `2.1.0` for cache invalidation.

- [ ] **Step 1: Write failing normalization and contract tests**

```python
def test_month_march_is_not_normalized_to_architecture_degree():
    assert ResumeNormalizer._canonical_degree("March 2025 – till date") is None
    assert ResumeNormalizer._canonical_degree("M.Arch") == "M.Arch"
    assert ResumeNormalizer._canonical_degree("Master of Architecture") == "M.Arch"

def test_normalizer_preserves_validated_record_count_and_provenance():
    raw = {"education": VALID_EDUCATION, "projects": VALID_PROJECTS}
    normalized = ResumeNormalizer.normalize(raw, "").model_dump(mode="json")
    assert len(normalized["education"]) == len(VALID_EDUCATION)
    assert normalized["education"][0]["source_section"] == "education"
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd backend && uv run pytest tests/unit/services/test_resume_section_integrity.py tests/unit/schemas/test_api_contracts.py -q`

- [ ] **Step 3: Make degree canonicalization token-safe**

Return `None` when a value contains no recognized degree token. Separate case-sensitive compact abbreviations from case-insensitive long-form names so month names cannot match degree abbreviations.

- [ ] **Step 4: Add provenance and integrity contract fields**

Add optional `source_section`, `source_heading`, and evidence fields to normalized record schemas, plus an additive typed extraction-integrity schema in CV result contracts. Existing payloads without these fields remain valid.

- [ ] **Step 5: Bump extraction versions**

Set `EXTRACTION_PARSER_VERSION="1.1.0"` and `EXTRACTION_SCHEMA_VERSION="2.1.0"`; existing cache-version comparisons then force incompatible results through reanalysis.

- [ ] **Step 6: Run normalization/contract/cache tests and Ruff**

Run:

```bash
cd backend
uv run pytest tests/unit/services/test_resume_section_integrity.py tests/unit/schemas/test_api_contracts.py tests/unit/core/test_unified_analysis_fingerprint.py -q
uv run ruff check app/services/resume_normalizer.py app/schemas/normalized_resume.py app/schemas/cv.py app/core/config.py
```

---

### Task 3: Downstream recommendation integrity and operational logging

**Files:**
- Modify: `backend/app/services/evidence_ranker.py`
- Modify: `backend/app/services/recommendation_service.py`
- Modify: `backend/app/services/cv_service.py`
- Test: `backend/tests/unit/services/test_recommendation_section_integrity.py`
- Test: `backend/tests/unit/services/test_resume_section_integrity.py`

**Interfaces:**
- Consumes canonical validated project/education collections and extraction-integrity metadata.
- Produces PII-safe aggregate extraction logs.
- Produces semantically deduplicated qualification gaps and ambiguity-safe Interview Focus/talent pools.

- [ ] **Step 1: Write failing recommendation tests**

```python
def test_rejected_projects_do_not_create_project_strength():
    strengths = EvidenceRanker.rank_strengths(skills_list=[], education_list=[], projects_list=[])
    assert not any("Project Experience" in value for value in strengths)

def test_interview_focus_preserves_acronyms_and_department_ambiguity():
    result = build_recommendations(CANDIDATE_WITH_AMBIGUOUS_DEPARTMENT)
    assert any("SAP" in value and "DCS" in value for value in result["interview_focus_areas"])
    assert not result["talent_pools"]
    assert any("clarify" in value.lower() for value in result["interview_focus_areas"])
```

- [ ] **Step 2: Run focused tests and verify RED**

Run: `cd backend && uv run pytest tests/unit/services/test_recommendation_section_integrity.py -q`

- [ ] **Step 3: Gate evidence and deduplicate gaps**

Pass only validated projects into strength generation. Deduplicate missing qualifications by normalized requirement text after removing presentation prefixes such as `Missing Skill:` and `Skill Gap`.

- [ ] **Step 4: Preserve acronyms and uncertainty**

Replace `.title()` presentation with acronym-aware labels. When no authoritative main department exists or manual department review is required, produce a clarification focus and suppress definitive talent-pool assignment.

- [ ] **Step 5: Add bounded extraction-integrity logging**

Emit a single structured log per completed extraction with candidate/run identifiers, accepted counts, rejected reason counts, duplicate counts, policy version, and validation duration. Do not include raw record values.

- [ ] **Step 6: Run focused recommendation/service tests and Ruff**

Run:

```bash
cd backend
uv run pytest tests/unit/services/test_recommendation_section_integrity.py tests/unit/services/test_resume_section_integrity.py -q
uv run ruff check app/services/evidence_ranker.py app/services/recommendation_service.py app/services/cv_service.py tests/unit/services/test_recommendation_section_integrity.py
```

---

### Task 4: Authoritative frontend mapping and Projects/Education rendering

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/utils/candidateDetail.ts`
- Modify: `frontend/src/app/candidates/[id].tsx`
- Modify: `frontend/src/__tests__/candidateDetailEnrichment.test.ts`

**Interfaces:**
- Consumes Task 2 extraction-integrity/version metadata and canonical normalized/raw collections.
- Produces one deduplicated `CandidateEducationView[]` and `CandidateProjectView[]`.
- Produces pure compact/expanded visibility calculations used by the page.

- [ ] **Step 1: Add failing frontend runtime assertions**

```typescript
const integrityCandidate = buildCandidateDetailViewModel(INTEGRITY_PAYLOAD);
assertEquals(integrityCandidate.education, [
  { degree: 'B.E.', institution: 'GTU', dates: '2019', grade: '7.59 CGPA' },
  { degree: 'H.S.C', institution: 'GHSEB', dates: '2015', grade: '63%' },
  { degree: 'S.S.C', institution: 'GSEB', dates: '2013', grade: '67.5%' },
]);
assertEquals(integrityCandidate.projects, []);

const legacyCandidate = buildCandidateDetailViewModel(LEGACY_CROSS_MAPPED_PAYLOAD);
assertEquals(legacyCandidate.projects, []);
assertEquals(legacyCandidate.education.length, 0);
```

- [ ] **Step 2: Run frontend test and verify RED**

Run the repository's existing candidate-detail runtime command from `frontend/AGENTS.md` or its current test harness entry.

- [ ] **Step 3: Implement authoritative source selection and legacy defense**

When new integrity metadata is present, select normalized validated records without unioning raw data. For legacy payloads, apply generic semantic validation and canonical fingerprints before merging. Support typed normalized field envelopes without converting arrays or objects into display text.

- [ ] **Step 4: Correct Projects and Education presentation**

Render project bullet points. Limit projects in compact mode, compute counts from rendered canonical collections, show the expansion button only when content is hidden, and preserve the empty-state message for zero projects.

- [ ] **Step 5: Run frontend runtime, type, and lint checks**

Run:

```bash
cd frontend
npm run lint
npx tsc --noEmit
```

Also run the existing candidate-detail runtime test command identified from repository test configuration.

---

### Task 5: Bulk-safe regression, compatibility, and operational handoff

**Files:**
- Create: `backend/scripts/audit_resume_section_integrity.py`
- Create: `backend/tests/unit/scripts/test_audit_resume_section_integrity.py`
- Modify: `README.md`
- Modify: `workstats.md` by appending a new sequential completion entry

**Interfaces:**
- Provides a read-only-by-default audit command over stored result JSON.
- Optional reprocessing mode delegates to existing reanalysis APIs/services, requires an explicit flag, and supports batch size plus continuation cursor.

- [ ] **Step 1: Write failing audit-command tests**

```python
def test_audit_defaults_to_read_only_and_reports_reason_counts(tmp_path):
    result = run_audit(results_dir=tmp_path, batch_size=100, reprocess=False)
    assert result.reprocessed == 0
    assert result.scanned >= 0

def test_audit_bounds_batch_size():
    with pytest.raises(ValueError):
        run_audit(results_dir=Path("results"), batch_size=1001, reprocess=False)
```

- [ ] **Step 2: Run audit tests and verify RED**

Run: `cd backend && uv run pytest tests/unit/scripts/test_audit_resume_section_integrity.py -q`

- [ ] **Step 3: Implement dry-run-first auditing**

Scan result files incrementally, report schema versions and integrity anomalies, never load all CVs into memory, and require `--reprocess` for mutations. Reprocessing must use the existing candidate reanalysis workflow rather than rewriting result JSON directly.

- [ ] **Step 4: Document rollout**

Document dry-run audit, bounded reprocessing, monitoring signals, rollback by version pinning, and the fact that production reprocessing is not executed automatically.

- [ ] **Step 5: Run complete targeted verification**

Run:

```bash
cd backend
uv run pytest tests/unit/services/test_resume_section_integrity.py tests/unit/services/test_resume_field_extractor.py tests/unit/services/test_recommendation_section_integrity.py tests/unit/scripts/test_audit_resume_section_integrity.py tests/unit/schemas/test_api_contracts.py -q
uv run ruff check app/services/resume_sections.py app/services/resume_field_extractor.py app/services/resume_normalizer.py app/services/evidence_ranker.py app/services/recommendation_service.py app/services/cv_service.py app/schemas/normalized_resume.py app/schemas/cv.py scripts/audit_resume_section_integrity.py tests/unit/services/test_resume_section_integrity.py tests/unit/services/test_recommendation_section_integrity.py tests/unit/scripts/test_audit_resume_section_integrity.py
cd ../frontend
npm run lint
npx tsc --noEmit
```

- [ ] **Step 6: Verify the reported candidate fixture and diff integrity**

Run the deterministic extractor against the synthetic equivalent of the reported layout and assert three education records, zero projects, and no rejected value exposed as a candidate fact. Run `git diff --check` and inspect `git diff --stat` plus the complete focused diff.

- [ ] **Step 7: Append the completion entry to `workstats.md`**

Record exact files, behavior, executed verification commands, pass counts, and any verification not performed. Do not alter Entries #001–#075.
