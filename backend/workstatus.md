# Work Status

## Work Completed
- Implemented normalized configuration hydration in `ConfigurationService.create_profile()`.
- Added PostgreSQL migrations (`008_normalized_rule_tables.sql`) for normalized rule tables.
- Corrected every MSSQL model by setting `__table_args__ = {"schema": "AIRIS"}` on all classes in `org.py` and `recruit.py`.
- Replaced aggregates depending on nonexistent tables (removed `workflow_states` from `mssql_aggregates.py`).
- Fixed the `SkillMaster.designations` mapper relationship in `taxonomy.py` by adding `cascade="all, delete-orphan"`.
- Removed all executable MSSQL branches from the migration runner (`run_migrations.py`).
- Added `match_status` to `EnrichedCandidateAnalysis` interface in `frontend/src/types/api.ts`.

## Files Changed
- `backend/app/services/configuration_service.py`
- `backend/scripts/migrations/postgres/008_normalized_rule_tables.sql` (NEW)
- `backend/scripts/migrations/postgres/008_normalized_rule_tables_down.sql` (NEW)
- `backend/app/models/org.py`
- `backend/app/models/recruit.py`
- `backend/app/repositories/mssql_aggregates.py`
- `backend/app/models/taxonomy.py`
- `backend/scripts/run_migrations.py`
- `frontend/src/types/api.ts`

## Pending Work
- None for the P0 startup fixes.

## Important Decisions
- To hydrate the normalized `RuleComponent`, `SystemRule`, `RuleCondition`, `RuleThreshold`, `RulePenalty`, `RuleWeight` tables, Pydantic objects from `UnifiedRuleConfig` were flattened and iterated dynamically inside `ConfigurationService.create_profile()`.
- Due to MSSQL functioning strictly as a read-only data source, all MSSQL-specific execution logic in the migrations runner was stripped out to ensure clarity and safety.

---

## Final Evidence-Based Audit (2026-08-07) — No code changed

### Report/DB reconciliation
- Truth source: `public.cv_results` (15 rows). `cvai.*` taxonomy + `cvai.match_results`/`match_results_history` are empty; `integration.vacancy_snapshots` empty; vacancies live from MSSQL (107 active).
- 15 rows = 11 fully parsed/matched + 2 alias/orphan rows + 2 processing placeholders.
- Alias rows still present (script `audit_db_integrity.py` targets but cleanup not run): `cv_gptsuifgr321345678o9p_c369770...` (identical content/score to `cv_gptsuifgr321345678o9p`, 86.9), `cv_document_cv_ut1765894215` (orphan, `cv_id=cv_ut1765894215`, null resume_json).
- Processing placeholders: `cv_1760668444`, `cv_san1761727581_4f4334...`.
- Claimed third-pass artifacts (`adversarial_audit_runner.py`, `walkthrough.md`, prior 45,927-byte workstatus narrative) do not exist on disk or in git. `workstatus.md` was later overwritten (HEAD `b58b5dc`); only trace is this session's findings.

### Proven root causes (all reproducible)
1. **Mitesh Darji 0.1-yr**: header dates detached from 4 jobs (`dates=None`). `_parse_job_dates_strict` (experience_gap_service.py:572-584) parses job bullets via `DateIntervalParser`; bullet token **"RAID-5"** fuzzy-parses to `2000-01-05→2000-01-31` via dateutil `default=datetime(2000,1,1)` (date_interval_parser.py:143-149). Two canonical jobs overlap → 1 block, 1 month, 0.1 yrs, "0 gaps", confidence 1.0 → NO_MATCH with min-experience failures.
2. **Fabricated skill evidence** (`scoring_engine.py:174-185` sub-token loop): any single token in a sentence-like mandatory skill matches the whole skill at confidence 1.0. "2 to 3 years of experience in chemical plant." matched via the word "experience" for Dixant/PPC/Sandip (vac 1040); "HPLC knowledge" matched via "knowledge" for Urjitkumar (vac 1285); "QA documentation & Audit" via "documentation" for Chaitanya; "Plant Commission" via "plant" for Shahdab. `stop_phrases` (`e.g`, `etc`) auto-satisfy skills (Gtworks "Skill: e.g").
3. **Name extraction**: full_name = "Sr. Flutter Developer" (Sandip) and "Production Planning & Control" (PPC; actual Sheth Mehulkumar Bhadreshbhai).
4. **work_experience extraction**: Sandip 0 jobs, PPC 0 jobs (5 table jobs lost; QM 10.0 vs EGA 0.0), Dixant exp 2.0 vs CV ~5.7 yrs (Oct-2020→Jul-2024 + Aug-2024→present), Mitesh 4 jobs w/o dates.
5. **Cross-domain guard failed**: Utkarsh (software) → Lab Assistant - I (QC) 85.0 with `domain_mismatch_capped=false` (false "Laboratory knowledge" from "lab research"); Software Developer (1334) fails LINQ/ADO.NET not inferred. Chaitanya classified Production/Chemical Manufacturing but best match is QA team; Shahdab classified C&I but best is Process & Project.
6. **Sandip misclassification chain**: extraction loss → keyword classifier hit "healthcare/safety/environment" from Nurse Calling System project → EHS domain → Plant Assistant 80.7. Active Flutter vacancy (1065) that fits him exists and was matched by Gtworks 86.9.
7. **Over-correction NOT present**; instead under-correction/entitlement via fabricated matches. Valid NO_MATCHs (Sakshi fresher, Abdul Mannan desktop-support) are correct and auditable via `unsuitable_openings`.

### Files changed
- None (audit only). Data dumps: `/var/folders/_t/1yldlwc56xx2b79hjv8nxwnh0000gn/T/opencode/cvaudit/`.

### Pending work (fixes NOT applied, per no-code-change scope)
- Fix sub-token matching to require full-phrase/verified evidence; fix `_parse_job_dates_strict` bullet fallback to reject bogus (year-2000) intervals; attach header dates to jobs; fix name/title extraction; infer absent tech skills (LINQ/ADO.NET); enforce domain guard consistently; re-run `reprocess_all_cvs.py` + `audit_db_integrity.py` cleanup after fixes.

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
