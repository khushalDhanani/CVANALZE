<truncated 54 lines>

---

## Fix-All Implementation (2026-08-07)

### Root causes fixed
1. **Sub-token skill fabrication** — `scoring_engine.py:_extract_term_matches`. Sub-token fallback now requires ALL meaningful tokens (≤3) of a short skill phrase to appear; a single shared token no longer matches ("HPLC knowledge" requires "HPLC" AND "knowledge"). Long phrases/sentences (≥6 words) and years-of-experience clauses ("2 to 3 years of experience...") are skipped entirely (can neither match nor fail).
2. **Stop-phrase auto-match** — `e.g`/`etc`/prose JD fragments are skipped (never SATISFIED, never FAILED) via new `match_evaluators.is_ignorable_requirement()`; shared by the `RequirementEvaluator` req loop and `_extract_term_matches`.
3. **RAID-5/2000-date fabrication** — `date_interval_parser.py:141-148` fuzzy fallback now requires an explicit date anchor (month name or 2/4-digit year token) AND rejects results whose year came from the `datetime(2000,1,1)` sentinel. `experience_gap_service.py` bullet fallback additionally requires a 4-digit year in the bullet text before parsing.
4. **Dead cross-domain guard** — `job_context.is_non_it_job`/`has_software_req` were computed but never consumed. `CrossDomainGuardEvaluator.evaluate` (match_evaluators.py) now caps an IT/software candidate (`context.is_software_cand`) matched to a non-IT vacancy even when taxonomy metadata is "Unknown", using `has_software_req` + IT-vacancy title/department heuristics (`_IT_VACANCY_RE`). Utkarsh→QC Lab Assistant now capped (85.0 → ~12.8); genuine IT vacancies (CIS/Software) remain uncapped.
5. **PPC table jobs** — `resume_field_extractor._extract_employment` now handles 2-cell markdown tables (`| Company + Title | Dates |`), splitting the merged first cell at the first title keyword (`_TITLE_KEYWORD_SPLIT_RE`).

### Not fixed (documented limitations)
- **Header-date attachment** for Mitesh's detached job dates: with the RAID-5 fix his jobs now resolve to UNKNOWN dates (honest 0.0 verified / hr_review) rather than fabricated 1 month. Attaching top-of-CV date lists to jobs is heuristic and not implemented.
- **Absent-tech inference** (LINQ/ADO.NET for Software Developer 1334) — not inferred; out of scope for these evidence fixes.
- Name/title extraction was already correct in current code (verified live: "Santosh Koli", "Sheth Mehulkumar Bhadreshbhai", "Utkarsh Patil" all HIGH); stored `cv_results` rows are stale and need a reprocess.

### Files changed
- `backend/app/services/scoring_engine.py`
- `backend/app/services/match_evaluators.py`
- `backend/app/services/date_interval_parser.py`
- `backend/app/services/experience_gap_service.py`
- `backend/app/services/resume_field_extractor.py`
- `backend/tests/test_scoring_engine.py`, `test_domain_matching.py`, `test_date_interval_parser.py`, `test_experience_date_formats.py`, `test_experience_gap_analysis.py`

### Verification
- Fixes verified via ad-hoc scripts: "HPLC knowledge"/"QA documentation & Audit"/"Plant Commission" no longer match on a single token; prose clauses & stop-phrases skipped; single-token skills still match; `RAID-5` → no interval; bullet fallback requires explicit year; 2-cell tables extract 3 jobs with correct company/title; IT candidate capped against QC vacancy (85.0→12.8) but NOT against CIS Software vacancy (90.0→90.0).
- Regression tests added and passing for every fix.
- Full-suite failure set is IDENTICAL to pre-change baseline (36 failed / 369 passed / 4 errors) — verified via stashed-baseline run + diff. All baseline failures pre-date this work (e.g. `test_overlapping_and_same_month_roles`, `test_two_stage_matching` suite, `test_cross_domain_guard_db_driven.test_same_family_is_compatible` unpacking a 3-tuple, `test_scale_benchmark`, `test_shadow_validation`, etc.). `test_genuine_active_vacancy_match` is environment-flaky (60s Ollama optimized-match timeout misclassifies the Flutter candidate as Chemical R&D); fails identically on unmodified source.

### Pending
- Re-run `scripts/reprocess_all_cvs.py` and run `scripts/audit_db_integrity.py` cleanup (alias/orphan rows: `cv_gptsuifgr321345678o9p_c369770...`, `cv_document_cv_ut1765894215`) once the pipeline is re-processed; then re-verify the 8 audit cases against the refreshed `cv_results`.
- Attach header-date lists to jobs for Mitesh-like CVs (future work).
6. **Domain Misclassification (Sandip & Chaitanya)** — Sandip was misclassified to `Environment Health & Safety` because keywords like "healthcare" and "hospital" in his project descriptions overpowered his IT skills. Fixed in `TaxonomyClassifier` and `CandidateDomainService` by applying a **10x weight multiplier** to keywords found directly in the candidate's `experience_titles`, `current_role`, and `summary`. Sandip is now correctly classified into `CIS Team`. Chaitanya remains in `Chemical Manufacturing` due to an upstream LLM extraction limitation where his job titles are parsed as `None`, so the title multiplier cannot apply.

### Final Audit Run Completed
- Reprocessed all 13 active CVs through `reprocess_all_cvs.py`. 
- Result: **TOTAL=13 | PASS=9 | WARNING=4 | FAIL=0**.
- The `WARNING`s were expected cases of "Zero skills extracted" for certain malformed CVs.
- DB cleanup and reprocessing is complete, and `cv_results` is now fully synchronized with the fixes.

---

## Dynamic Match Quality Fixes (2026-08-10)

### Root Causes Fixed

Triggered by `cv_1761281901_CandidateCVFileName_13595` (Shubham Gavhane — ITI Fitter) surfacing
72.3% POTENTIAL_MATCH for "Plant Assistant - I (Maintenance)" but 0% everywhere else.

1. **Job title label-prefix denylist** — `resume_field_extractor.py`
   - Added module-level `_LABEL_PREFIX_DENYLIST` frozenset (duration, period, designation, position, etc.).
   - `is_valid_job_title()` now rejects any candidate string that is a bare label token (e.g. `"Duration:"` → False).
   - `_extract_employment()` enhanced to extract an embedded role title from compound Duration bullets: `"Duration :- Fitter Executive , July 2021 - Present"` now correctly sets `job_title = "Fitter Executive"`.

2. **Sparse-CV maintenance skill inference** — `scoring_engine.py`
   - Three module-level frozensets added (`_MAINTENANCE_CV_SIGNALS`, `_MAINTENANCE_INFERRED_TERMS`, `_MAINTENANCE_INFERENCE_EXCLUDED`).
   - `_extract_term_matches()` now credits maintenance-family required skills (e.g. "Plant Maintenance", "Fitter", "Maintenance Work") as inferred matches for CVs < 3000 chars that contain ITI/trade signal words.
   - Non-maintenance skills (chemistry, QA, SAP, electrical, etc.) are never inferred.

3. **Sub-family domain mismatch relaxation** — `match_evaluators.py`
   - Added `CrossDomainGuardEvaluator._share_root_family()` static method.
   - Vacancies whose family is a numbered sub-team of the candidate's root family (e.g. `"Maintenance Team - 1 (Ramesh Maurya)"` vs `"Maintenance Team"`) no longer trigger the -50pt domain mismatch cap.
   - The check strips trailing parenthetical owner qualifiers and trailing `-N` suffixes before comparing roots.

4. **Promote MEDIUM scores to suitable_openings** — `scoring_engine.py`
   - `analyze_cv()` now includes MEDIUM-classified matches (score ≥ `match_medium_threshold`, not domain-capped, no mandatory failures) in `suitable_openings`.
   - `best_match` will now point to the highest-scoring MEDIUM match when no HIGH match exists, making `has_genuine_match = True` for candidates like Shubham.

### Files Changed
- `backend/app/services/resume_field_extractor.py`
- `backend/app/services/scoring_engine.py`
- `backend/app/services/match_evaluators.py`

### Verification
- All 3 files pass Python AST syntax check (`python3 -c "import ast; ast.parse(...)`).
- **Pending**: restart backend API, delete CV cache, reprocess `cv_1761281901_CandidateCVFileName_13595`, confirm:
  - `work_experience[*].job_title` = `"Fitter Executive"` (not `"Duration:"`)
  - `suitable_openings` count ≥ 1
  - `has_genuine_match = true`
  - `domain_mismatch_capped = false` on Maintenance sub-team vacancies

---

## Domain Taxonomy & LLM Hierarchy Fixes (2026-08-12)

### Root Causes Fixed
1. **Tri-State Hierarchy Rejection Bug** — `VacancyFitEvaluator`. `is_hierarchy_valid` was incorrectly coercing "Unknown" (insufficient evidence) into `False`, causing strong matches to fail the `has_genuine_match` test. Updated to use tri-state logic (`True`, `False`, `None`) where `None` signifies unknown and DOES NOT block a match. Fixed regression tests accordingly.
2. **KeywordConfig Schema Mismatch in Legacy Tests** — `test_department_domain_repository.py`. Tests were asserting `assert kw in it.keywords`, but keywords are now modeled as `KeywordConfig` objects instead of strings. Tests have been updated to check `k.term`.
3. **Gemma Domain Output Override Over Strong Deterministic Domain** — `CandidateAnalysisContext`. The candidate's deterministically classified domain was incorrectly getting overwritten by Gemma's unvalidated `professional_domains` output even when deterministic confidence was high. Implemented strict precedence rules: deterministic classification takes precedence. Gemma can suggest a domain only if it's explicitly backed by keyword evidence from the CV in `CandidateDomainService._has_domain_evidence`. Fixed test environments so that mock domains don't trigger broken Ollama embedding calls.

### Files Changed
- `backend/app/services/candidate_domain_service.py`
- `backend/app/services/match_evaluators.py`
- `backend/tests/test_domain_matching.py`
- `backend/tests/test_department_domain_repository.py`

### Verification
- `tests/test_domain_matching.py` successfully passes all regression tests, correctly asserting `None` logic and preventing Gemma hallucinations from overriding deterministic taxonomies.
- `tests/test_department_domain_repository.py` passes completely. Mock `DynamicTaxonomyService` was put in place to ensure Ollama availability does not fail legacy test suites.
