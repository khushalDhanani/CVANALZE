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
- **Fixed "Experience & Seniority: N/A" & Calculation Bugs (Generic Cross-Platform Pipeline)**:
  - Created reusable `DateIntervalParser` module (`date_interval_parser.py`) supporting locale-aware date parsing (English, Spanish, French, German), ISO dates, seasons/quarters, fuzzy strings, 2-digit years, parenthetical ranges, and present synonyms (`present`, `current`, `till date`, `onwards`, `heute`, `aujourd'hui`).
  - Integrated `DateIntervalParser` into `ResumeNormalizer` (`resume_normalizer.py`) to output typed `NormalizedDateInterval` objects with confidence levels and evidence lists.
  - Fixed premature `commit()` logic in `ResumeFieldExtractor._extract_employment()` (`resume_field_extractor.py`) so multi-line job headers are joined with dates instead of being split.
  - Implemented `ExperienceCalculator.calculate_canonical_experience()` (`experience_calculator.py`):
    1. Preserves raw employment text and raw date strings.
    2. Logs unparsed dates with candidate ID, role index, and raw string (`[EXPERIENCE_DATE_PARSE_UNSUPPORTED]`).
    3. Handles ongoing/present roles by defaulting to current date.
    4. Merges overlapping employment intervals without double-counting.
    5. Counts same-month roles as at least 1 active month.
    6. Ensures deterministic date-derived experience is authoritative and cannot be overridden by LLM or stated experience.
    7. Derives canonical seniority levels (`Executive / Director`, `Lead / Principal`, `Senior`, `Mid-Level`, `Junior / Associate`, `Entry Level`).
    8. Documented employment roles never default to `0.0`, `Junior`, or `N/A` (falls back to stated experience or role-count heuristic if dates are unparseable).
  - Exposed top-level `experience_years`, `seniority`, `experience_summary`, and `work_experience` across `cv_service.py`, `candidates.py` (`GET /api/v1/candidates/{id}`), and `recommendation_service.py`.
  - Updated frontend `[id].tsx` to render Experience & Seniority badge in the candidate header bar, Experience Timeline with fallback keys, and Hiring Intelligence assessment text directly.
  - Added new regression test suites `test_date_interval_parser.py`, `test_experience_date_formats.py`, and `test_experience_canonical.py` (15/15 unit tests passing 100%).
- **Fixed Candidate Directory Missing Scanned CVs Bug (Redis + Disk Result Merging)**:
  - Discovered that candidate result records stored in Redis (`cv_gptsuifgr321345678o9p.json` and `cv_ut1765894215.json`) were being ignored because `ResultRepository.list_all_results()` previously only scanned disk files in `uploads/results/`.
  - Updated `ResultRepository.list_all_results()` (`result.py`) to merge Redis cache entries (`cv_result:*.json`) with disk files, deduplicating by candidate/scan ID.
  - Added `./backend/uploads:/app/uploads` volume mount to both `api` and `worker` in `docker-compose.local.yml`.
  - Rebuilt containers (`docker compose up -d --build api worker`). Candidate search now returns all 5 candidates (`cv_Utkarsh_Patil_07012026sdfgdfvdfsf`, `cv_gptsuifgr321345678o9p`, `cv_ut1765894215`, `candidate-1`, `candidate-2`).
- **Updated `run.md`**:
  - Added Docker Compose full-stack startup commands.
  - Added Docker container rebuild command (`up -d --build api worker`) for updating backend changes.
  - Added log monitoring and container management commands.

## Files Changed
- `docker-compose.yml`
- `docker-compose.local.yml` — added `./backend/uploads:/app/uploads` volume mounts for `api` and `worker`
- `run.md` — updated with Docker Compose commands, container rebuild steps, and log monitoring
- `backend/app/repositories/result.py` — updated `ResultRepository.list_all_results()` to scan both Redis cache and disk files
- `backend/app/schemas/analysis.py` — added `unsuitable_openings` field to `EnrichedCandidateAnalysis`
- `backend/app/schemas/match.py` — added `unsuitable_openings` field to `CandidateMatchAnalysis`
- `backend/app/services/date_interval_parser.py` — new generic locale-aware date interval parsing module
- `backend/app/services/candidate_search_service.py` — normalized status filter matching in candidate search
- `backend/app/services/match_service.py` — split evaluated matches by classification threshold
- `backend/app/services/scoring_engine.py` — split evaluated matches by classification threshold
- `backend/app/services/resume_field_extractor.py` — expanded `_DATE_RANGE` regex and fixed `_extract_employment` entry commit logic
- `backend/app/services/experience_calculator.py` — integrated `DateIntervalParser`, canonical calculation, unparsed date logging, and interval merging
- `backend/app/services/resume_normalizer.py` — integrated `DateIntervalParser` for typed `NormalizedDateInterval`
- `backend/app/services/cv_service.py` — attached top-level `experience_years`, `seniority`, `experience_summary`, and `work_experience`
- `backend/app/api/candidates.py` — dynamically attached canonical experience on candidate detail endpoint for legacy records
- `backend/app/services/recommendation_service.py` — multi-tier fallback using canonical experience calculator
- `frontend/src/app/candidates/[id].tsx` — added Experience & Seniority header badge + classification-aware labels + Experience Timeline schema alignment
- `backend/tests/test_date_interval_parser.py` — new test suite for locale-aware date parsing
- `backend/tests/test_experience_date_formats.py` — new test suite for date extraction formats
- `backend/tests/test_experience_canonical.py` — new test suite for canonical experience calculation

## Pending Work
- None currently.

## Important Decisions
- **Redis + Disk Result Merging**: `ResultRepository.list_all_results()` now scans Redis keys `cv_result:*.json` in addition to disk files, so candidates saved in Redis cache immediately show up in the candidate list UI even if saved prior to volume mounting.
