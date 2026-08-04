# Work Status

## Work Completed
- Diagnosed the root cause of the UI only displaying 5 vacancies. The application was failing to connect to the MSSQL database and was returning a fallback mock list.
- Identified that the failure was due to missing `pyodbc` Microsoft drivers (`msodbcsql18`) in the Docker image and missing `DB_*` environment variables in `docker-compose.yml`.
- Updated `docker-compose.yml` to pass down MSSQL database credentials (`DB_SERVER`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`).
- Updated `docker-compose.local.yml` to set `INSTALL_MSSQL_ODBC: "true"` for both `api` and `worker` services.
- Successfully rebuilt and restarted the `api` and `worker` docker containers. The build downloaded and installed the necessary Debian MS ODBC packages.
- **Fixed "SUITABLE JOB MATCH" mislabeling bug**:
  - Backend: Split `evaluated_matches` into `suitable_openings` (HIGH/MEDIUM) and `unsuitable_openings` (LOW) in both `MatchService` and `ScoringEngine`.
  - Backend: Added `unsuitable_openings` field to both `EnrichedCandidateAnalysis` and `CandidateMatchAnalysis` schemas.
  - Frontend: Replaced hardcoded index-based label with classification-aware labels (HIGH → "Top Job Match"/"Strong Match", MEDIUM → "Potential Match").
  - Frontend: Added "Manual Review Required" section for LOW-classified vacancies with warning styling.
- **Fixed "Experience & Seniority: N/A" & Incorrect Gaps Bug**:
  - Backend `resume_field_extractor.py`: Expanded `_DATE_RANGE` regex to extract full dates (`15/06/2018`), unspaced ranges (`2018-2021`), 2-digit end years (`2018 - 21`), quarters/seasons (`Q1 2020`), and present synonyms (`till date`, `onwards`, `till now`).
  - Backend `resume_field_extractor.py`: Fixed `_extract_employment` commit logic so multiple roles with dates in CV text are not overwritten into a single role.
  - Backend `experience_calculator.py`: Enhanced `_parse_date` and `_extract_date_range` to support unspaced hyphens, 2-digit short years, quarters/seasons, and full dates; updated `interval_duration_months` to return at least 1 month for valid same-month intervals.
  - Backend `recommendation_service.py`: Upgraded `exp_years` resolution to multi-tier fallback (`quality_metrics.experience_years` -> `normalized_resume.experience.deterministic_years` -> `stated_years` -> `calculate_total_experience()` -> employment role count). Prevents 0.0 Junior fallback when experience exists.
  - Frontend `[id].tsx`: Updated Experience Timeline card to support `work_experience`, `experience`, and `normalized_resume.employment` schema keys (`exp.company`, `exp.dates`, `exp.interval`).
  - Added new unit test suite `test_experience_date_formats.py` (100% pass).

## Files Changed
- `docker-compose.yml`
- `docker-compose.local.yml`
- `backend/app/schemas/analysis.py` — added `unsuitable_openings` field to `EnrichedCandidateAnalysis`
- `backend/app/schemas/match.py` — added `unsuitable_openings` field to `CandidateMatchAnalysis`
- `backend/app/services/match_service.py` — split evaluated matches by classification threshold
- `backend/app/services/scoring_engine.py` — split evaluated matches by classification threshold
- `backend/app/services/resume_field_extractor.py` — expanded `_DATE_RANGE` regex and fixed `_extract_employment` entry commit logic
- `backend/app/services/experience_calculator.py` — enhanced `_parse_date`, `_extract_date_range`, and `interval_duration_months`
- `backend/app/services/recommendation_service.py` — multi-tier fallback for experience years & seniority assessment
- `frontend/src/app/candidates/[id].tsx` — classification-aware labels + unsuitable openings section + Experience Timeline schema alignment
- `backend/tests/test_experience_date_formats.py` — new test suite for date extraction formats

## Pending Work
- None currently.

## Important Decisions
- Completed candidate detail page (`/candidates/[id].tsx`) frontend implementations based on the approved plan.
- Rendered extracted candidate skills as Badges below the certifications card.
- Replaced the single "Best Match Vacancy" card with a full iteration of all `suitable_openings`, displaying score badges and component score bars for each.
- Added deep AI reasoning rendering (`llm_reason`) and `missing_skills` gap analysis for all match cards.
- Refactored `HrReviewModal` logic to support dynamic selection of any suitable opening for review, instead of only the best match.
- Updated `CandidateSearchOptions` type in `api.ts` to include missing backend filters (location, skills, education, status, min_similarity, limit).
- Expanded filter UI on `/candidates/index.tsx` to utilize the new backend parameters.
- Synced state changes for all new filters with URL query parameters to maintain URL parity and easy sharing.
- Noted the absence of backend API endpoints for DELETE/UPDATE, omitting UI implementation of those actions until the backend supports them.
- Addressed missing candidate profile mapping via `CandidateProfileSummary.tsx`.
- Integrated `inferred_skills`, `matched_skills`, and `missing_skills` rendering into `MatchAnalysisCard.tsx`.
- Refactored `useCvUpload.ts` to detect `CACHE_HIT` and supply a `forceReanalyze` escape hatch to bypass cache and resubmit.
- Integrated file size validation (10MB) into `cv-match.tsx` before uploads occur.
- **Experience Bug Resolution**: Resolved date parsing limitations, extraction commit overwriting, single-point-of-failure in recommendation service, and frontend field key mismatches.
