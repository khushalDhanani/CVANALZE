# CV Analyzer — End-to-End System Diagnostic Report

**Date:** July 29, 2026  
**Status:** Diagnostic Only (No Code Modifications Applied)  

---

## 1. Stack & Architecture

### Actual Tech Stack vs Expected

| Layer | Component / Tech | Configuration & Details | Confirmed State |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | FastAPI (Python 3.12) | Uvicorn server, Pydantic v2, `pydantic-settings` | Confirmed |
| **Database & ORM** | MSSQL (`AIRIS_TEST`) | SQLAlchemy 2.0 ORM with `pyodbc` (`ODBC Driver 18 for SQL Server`), Server `172.25.1.160:1433` | **Confirmed live MSSQL DB** (Fallback to `DEFAULT_JOB_OPENINGS` if DB unreachable) |
| **Task Queue & Worker** | Redis + `rq` | `start_worker.py` concurrent background workers with PubSub progress streaming | Confirmed |
| **CV Document Parsing** | Docling (`docling` v2.115.0) | `DocumentConverter` with dynamic RapidOCR fallback (`RapidOcrOptions`) | Confirmed |
| **LLM Integration** | Ollama HTTP API (`httpx`) | Default model: `qwen3:4b`, Base URL: `http://localhost:11434` | Confirmed |
| **Frontend Framework** | React Native / Expo | Expo Router v4, Expo SDK 52, React 18 (Cross-platform Web & Mobile targets) | Confirmed |
| **Frontend Styling & UI** | NativeWind v4 + Lucide Icons | Tailwind CSS design system tokens (`UI.md`), `lucide-react-native`, `@expo-google-fonts/inter` | Confirmed |

### Repository Folder Structure

```
cv-analyzer/
├── AGENTS.md                   # Repository guidelines & architectural constraints
├── README.md                   # Project overview
├── workstatus.md               # Phase progress & task history tracking
├── run.md                      # Service execution & worker launch guide
├── docker-compose.yml          # Local container setup (Redis)
├── backend/
│   ├── app/
│   │   ├── api/                # FastAPI endpoints (analysis, batch, config, cv, jobs)
│   │   ├── core/               # Configuration (config.py), database connection, logging, profiler
│   │   ├── models/             # SQLAlchemy ORM models (recruit.py, org.py, config.py)
│   │   ├── prompts/            # LLM prompt templates (optimized_match.py)
│   │   ├── repositories/       # Data access layer (job.py, result.py, llm_cache.py, config.py)
│   │   ├── schemas/            # Pydantic schemas (analysis, match, profile, job, config)
│   │   └── services/           # Business logic (scoring_engine, match_service, cv_service, document_parser, llm_service, vacancy_prefilter)
│   ├── main.py                 # FastAPI application entrypoint
│   ├── start_worker.py         # Concurrent RQ worker launcher
│   └── pyproject.toml / .env   # Environment & dependency manifests
└── frontend/
    ├── UI.md                   # Design system specification & component tokens
    ├── tailwind.config.js      # NativeWind theme tokens & font mappings
    └── src/
        ├── app/                # Expo Router screen routes (_layout, index, cv-match, vacancies, batch, config, explore)
        ├── components/ui/      # Compact UI design system primitives (Button, Card, DenseRow, Badge, TextField, ScoreBadge, HrReviewModal, SidebarLayout)
        ├── hooks/              # Custom React hooks (useJobs, useCvUpload, useMatchConfig, useBatchProgress)
        ├── services/           # API services (apiClient, cvService, matchService, jobsService, batchService, configService)
        └── types/              # TypeScript API contract definitions (api.ts)
```

---

## 2. CV Ingestion & Parsing Pipeline

### Extraction & Structuring Process

1. **File Ingestion & Validation:**
   - Accepts `.pdf` and `.docx` formats up to 15 MB (`MAX_FILE_SIZE_BYTES`).
   - Validates file extensions and checks magic byte signatures via `filetype`.
2. **Docling Document Conversion (`DocumentParser.parse`):**
   - Runs fast non-OCR `PdfPipelineOptions` first.
   - **Dynamic OCR Fallback:** If extracted markdown text length is under `AUTO_OCR_MIN_TEXT_CHARS` (100 characters), re-runs extraction using `RapidOcrOptions(force_full_page_ocr=True)`.
   - Exports raw markdown text (`export_to_markdown()`) and Docling structured document dictionary (`export_to_dict()`).
3. **Fields Extracted & Stored (`cv_service.process_cv_file`):**
   - **Identifiers & Metadata:** `id` / `cv_key` (SHA-256 hash-based), `filename`, `content_type`, `parsed_at`, `page_count`, `is_scanned`, `ocr_applied`.
   - **Content:** Full markdown text, raw text, `structured_doc`.
   - **Version Tracking:** `parser_version` ("1.0.0"), `schema_version` ("1.0.0").
4. **Caching & Integrity Mechanism:**
   - Results are atomically saved to `uploads/results/{cv_key}.json`.
   - Re-ingestion of an identical file triggers a **Cache Hit** (`status: "CACHE_HIT"`) without re-parsing or re-calling the LLM if `cv_hash`, `parser_version`, and `schema_version` match.

---

## 3. Matching & Scoring Engine Summary

### Engine Components & Weights

The scoring engine (`ScoringEngine.evaluate_job_match`) calculates a composite match score (0.0 to 100.0%) across 8 weighted components:

| Component | Default Weight | Evaluation Method |
| :--- | :--- | :--- |
| **Skills** | `25%` | Exact + regex term matching of required & preferred skills against CV text. |
| **Role / Title** | `15%` | Current candidate role vs target job title divergence (50% score if career transition detected). |
| **Experience** | `15%` | Candidate experience vs vacancy min/max bounds (linear score scaling below min, -20% penalty for overqualification). |
| **Domain** | `15%` | Department domain term overlap against candidate current role, skills, and CV section headers. |
| **Education** | `10%` | Extracted education degrees matched against specified vacancy education requirements. |
| **Technology** | `10%` | Specific technology keyword overlap ratio. |
| **Certification** | `5%` | Specified certification requirement match ratio. |
| **Responsibilities** | `5%` | Role responsibility keyword overlap ratio. |

*Note: Component weights are normalized dynamically based on active fields present in the vacancy definition (`coverage = active_weights / sum(weights)`).*

### Mandatory Requirements Enforcement

- **Evaluated Tiers:** Mandatory Skills, Minimum Experience Years, Education Requirement, Certification Requirement, Max CTC Budget.
- **Penalty Logic:**
  - Every failed mandatory requirement subtracts `MANDATORY_FAILURE_PENALTY_PER_ITEM` (**20.0 points**).
  - The overall score on any mandatory failure is capped at `MAX_SCORE_ON_MANDATORY_FAILURE` (**65.0%**).
  - Automatically flags `hr_review_required = True`.
- **False 100% Guard:** Any overall match score calculated at `100.0%` with missing criteria or incomplete skills is capped at `99.0%`.

### Domain Score Computation & Token-Overlap Status

- **Domain Computation:** Extracts department domain terms via `_extract_department_domain_terms()`, excluding administrative stop-words (`admin`, `department`, `development`, `management`, `operations`, etc.). Builds candidate domain text from current role, core skills, and CV headings.
- **Token-Overlap Status:** **Sub-string matching is still present.** The code uses `any(t in domain_candidate_text for t in dept_terms)` which checks string containment (`in`), meaning token-boundary isolation (`\b` word boundary regex matching) **has NOT landed yet** for domain scoring.

---

## 4. Live Data Quality Audit (MSSQL `AIRIS_TEST`)

A direct diagnostic query was executed against the live MSSQL Database (`172.25.1.160`):

| Diagnostic Check | Count / Finding | Details & Impact |
| :--- | :--- | :--- |
| **Total Active Vacancy Requests in DB** | **1,299** | Rows where `VacancyRequestIsActive = True`. |
| **Filtered Open Active Vacancies** | **106** | Active, non-deleted, non-closed, non-force-closed vacancies returned by `VacancyService.get_active_vacancies()`. |
| **Missing `RequestedAdditionalKnowledge`** | **66** (Raw active) / **0** (Filtered open) | In raw active records, 66 rows have `NULL` or empty skills. All 106 filtered open vacancies have text. |
| **Garbage / Placeholder Requirements** | **46** (Raw active) / **4** (Filtered open) | Values such as `"-"`, `"Yes"`, `"NO"`, `"N/A"` entered into skill requirement fields in DB. |
| **Missing Experience / CTC Ranges** | **0** | All 106 open active vacancies have valid experience and CTC ranges configured. |
| **Missing `JobProfileID`** | **358** (Raw active) / **0** (Filtered open) | Filtered open vacancies all link to valid `JobProfileID` records. |
| **Org Department Masters** | **52** | 52 total `OrgDepartmentMst` records, all unique (0 case-insensitive duplicates). |

> [!WARNING]
> **Data Quality Risk:** The 4 active open vacancies with garbage requirements (`"-"`) result in single-character requirement evaluations in the scoring engine.

---

## 5. LLM Layer & Optimization Pipeline

### Model & Timeout Setup

- **Configured Model:** `qwen3:4b` (configured in `Settings.OLLAMA_MODEL`).
- **Ollama Base URL:** `http://localhost:11434`.
- **Request Timeout:** `600.0` seconds (10 minutes).
- **Retry Setup:** Up to `3` retries on HTTP or JSON parsing failures (`OLLAMA_MAX_RETRIES = 3`).
- **LLM Context Parameters:** `num_predict: 4096`, `num_ctx: 8192`, `temperature: 0.1`, `think: False`, `keep_alive: "30m"`.

### Fast-Track / LLM Bypass (Confidence Gating)

Implemented in Phase 3 (`MatchService.analyze_single_cv`):
- Prior to calling Ollama, the deterministic `ScoringEngine` evaluates candidate matches against pre-filtered vacancies.
- If the top vacancy match has **Coverage ≥ 50%** (`LLM_SKIP_COVERAGE_THRESHOLD = 0.50`) and **Score Margin over 2nd place ≥ 15.0 points** (`LLM_SKIP_MARGIN_THRESHOLD = 15.0`), the system sets `llm_skipped = True` and **completely bypasses LLM inference**, cutting LLM latency to 0ms.

### Grammar-Constrained JSON Status

- **Current Status:** **NOT YET IN USE.**
- **Details:** Calls to Ollama pass `"format": "json"` in the request payload, which enables standard JSON mode in Ollama, but does **NOT** pass a schema object (grammar-constrained JSON Schema). The response is parsed via `json.loads()` and validated against Pydantic models post-inference.

---

## 6. Frontend Implementation Status vs `UI.md` Spec

### Built Screens & Components

- `app/_layout.tsx`: Root shell with Inter font loader (`@expo-google-fonts/inter`), `SidebarLayout` container, and splash screen handler.
- `app/index.tsx` (Home Screen): Hero card, Quick Stats grid (Active Vacancies, LLM Engine state, DB connection), Quick Workflows navigation, and detailed System Health & Services status.
- `app/cv-match.tsx` (Single CV Match): Dual-mode input (Paste Raw CV text or Native/Web file upload), LLM Semantic Enrichment toggle, Best Matched Job summary card with sub-score bars (`ComponentScoreBar`), candidate mandatory failure alerts, and HR review modal trigger (`HrReviewModal`).
- `app/vacancies.tsx` (Vacancies Directory): Search filter by title/department/skills, Indian Rupee (`₹` LPA) salary formatter, cache invalidation trigger.
- `app/batch.tsx` (Batch Processing): Batch file directory scanning with WebSocket real-time progress events.
- `app/config.tsx` (Config Screen): Weight tuning sliders for matching components, threshold inputs for LLM Bypass (Fast-Track).
- `components/ui/Sidebar/SidebarLayout.tsx`: Responsive navigation layout (permanent sidebar on desktop/tablet, drawer on mobile).

### Gaps & Drift vs Spec (`UI.md` & `workstatus.md`)

1. **Candidate List & Candidate Detail Screens:** **NOT BUILT.** There is currently no UI screen for viewing saved candidate match records or candidate profiles (`RecruitCandidateMst`).
2. **Home Screen Spec Completion:** Pending items from `workstatus.md` (Operational blockers "Needs Attention" panel, Recent Activity feed using `DenseRow`, Top Vacancies breakdown).
3. **Unused Boilerplate:** `frontend/src/app/explore.tsx` is an unused default Expo template route.

---

## 7. Known Open Issues Matrix

| Issue / Feature Gap | Description & Impact | Current Status |
| :--- | :--- | :--- |
| **Domain Scoring Token-Overlap** | `ScoringEngine._extract_department_domain_terms` cleans tokens, but matching in `evaluate_job_match` uses `t in domain_candidate_text` (raw substring search instead of word boundaries `\b`). | 🔴 **Untouched** |
| **Empty Requirements Denominator Bug** | Zero-skills or empty vacancy criteria causing division by zero or invalid weights. | 🟢 **Fixed** (Dynamic weight normalization & coverage fallback implemented) |
| **LLM Truncation & Schema Enforcement** | Ollama responses relying on `"format": "json"` without grammar-constrained schema definition. Long outputs may truncate (`num_predict: 4096`). | 🟡 **Partially Fixed** (Pydantic validation & retries added, schema grammar unconstrained) |
| **Vacancy Pre-filter Scaling** | Deterministic pre-filter (`O(V)`) narrows vacancies to top-K before LLM evaluation. Fast-track bypass skips LLM for unambiguous matches. | 🟢 **Fixed** (Precomputed cache tokens & fast-track implemented; ANN scaling deferred until ~3,000+ vacancies) |
| **Candidate List & Detail Screens** | Missing frontend screens for candidate directory, historical scan results browsing, and detailed profile views. | 🔴 **Untouched** |
| **Database Data Quality Noise** | 46 active DB vacancies contain garbage string requirements (e.g. `"-"`, `"Yes"`). | 🔴 **Untouched** (No backend DB cleaning/filter logic applied to stripped requirements) |

---
