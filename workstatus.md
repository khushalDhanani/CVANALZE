# CV Analyzer - Work Status

## Work Completed
- **Phase 1: Vacancy Caching**
  - Added in-memory caching to `JobRepository.get_all_jobs()` to eliminate repetitive DB queries per CV.
  - Decreased vacancy retrieval latency from ~1776ms to ~0.5ms.
- **Phase 2: Task Queue Architecture**
  - Installed `rq` and configured Redis as a message broker for distributed processing.
  - Replaced the synchronous loop in `main.py` with `scan_uploads_directory` enqueuing background tasks.
  - Implemented `start_worker.py` to spawn independent concurrent workers (fixed macOS fork safety issues).
  - Validated linear scaling of performance across 3 concurrent workers.
- **Phase 3: LLM Bypass (Confidence Gating)**
  - Implemented a configurable fast-track check using `ScoringEngine.evaluate_job_match()` prior to LLM processing.
  - Added `LLM_SKIP_MARGIN_THRESHOLD` (15.0) and `LLM_SKIP_COVERAGE_THRESHOLD` (0.50) to configurations.
  - Successfully bypassed 100% of LLM calls on standard unambiguous matches, cutting LLM latency (80s+) to 0ms.
- **Phase 4: Optimization Analysis**
  - Analyzed the Python regex pre-filter time complexity (strictly `O(V)`).
  - Determined that an embedding-based ANN filter (FAISS/pgvector) is unnecessary until vacancy counts hit roughly 3,000–5,000.
- **Phase 5: Frontend Tailwind CSS Setup (React Native / NativeWind v4)**
  - Installed `nativewind` and `tailwindcss` in `frontend`.
  - Configured `tailwind.config.js`, `metro.config.js` (`withNativeWind`), and `babel.config.js` (`jsxImportSource: 'nativewind'`).
  - Added `@tailwind base;`, `@tailwind components;`, `@tailwind utilities;` to `frontend/src/global.css`.
  - Imported `global.css` in `frontend/src/app/_layout.tsx`.
  - Added `nativewind-env.d.ts` and updated `tsconfig.json` for TypeScript type support.
- **Phase 6: Frontend API Integration Layer**
  - Configured platform-aware HTTP base client in `frontend/src/constants/config.ts` & `frontend/src/services/apiClient.ts`.
  - Created complete TypeScript contracts matching all backend Pydantic models in `frontend/src/types/api.ts`.
  - Implemented modular API services: `cvService`, `matchService`, `jobsService`, `batchService` (with WebSocket streaming), and `configService`.
  - Developed custom React hooks: `useJobs`, `useCvUpload`, `useMatchConfig`, and `useBatchProgress`.
- **Phase 7: Full Production UI & Vector Icons Migration**
  - Installed `@expo/vector-icons`.
  - Replaced all emoji characters across all screens (`index.tsx`, `cv-match.tsx`, `vacancies.tsx`, `batch.tsx`, `config.tsx`, `HrReviewModal.tsx`, `app-tabs.web.tsx`) with professional `Feather` vector icons.
- **Phase 8: Web Upload, Deprecation Warnings, Formatting & Icon Fixes**
  - Fixed Web browser `FormData` file upload handling in `apiClient.ts` to send valid `File`/`Blob` objects instead of stringified objects.
  - Added native browser file picker dialog in `cv-match.tsx`.
  - Replaced deprecated `shadow*` props in `app-tabs.web.tsx` with standard `boxShadow`.
  - Cleared invalid `Ionicons` name warnings.
  - Fixed `Cannot read properties of undefined (reading 'toLowerCase')` in `vacancies.tsx` using null-safe string fallbacks.
  - Fixed duplicate key warning in `vacancies.tsx` and `batch.tsx` `keyExtractor` with index fallbacks.
  - Implemented Indian Rupees (`₹`) formatting in `en-IN` locale and LPA handling in `vacancies.tsx`.
  - Replaced `dollar-sign` vector icon in `vacancies.tsx` with `FontAwesome5` `rupee-sign` icon.
  - Verified 0 TypeScript errors via `npx tsc --noEmit`.
- **Phase 9: Sidebar Navigation Refactoring**
  - Scaffolded a responsive `SidebarLayout` component complying with the `UI.md` compact design system.
  - Implemented automatic drawer management for phone-sized screens, alongside static sidebar behavior for larger screens.
  - Wired active route state directly to Expo Router's `usePathname()`.
  - Configured navigation actions to use `router.push()` from Expo Router.
  - Integrated `SidebarLayout` into the main application shell (`app/_layout.tsx`), replacing `AppTabs`.
- **Phase 10: Typography & Custom Fonts Loading**
  - Installed `@expo-google-fonts/inter` to support the custom fonts defined in `tailwind.config.js`.
  - Integrated `useFonts` within `app/_layout.tsx` to properly load `Inter_400Regular`, `Inter_500Medium`, `Inter_600SemiBold`, and `Inter_700Bold`.
  - Added robust font loading logic hooked with `expo-splash-screen` to prevent layout shift and missing font crashes on native builds.
- **Phase 11: Fleshing out the Config Screen (LLM Bypass Settings)**
  - Modified the backend `MatchEngineConfigUpdate` and `MatchEngineConfigResponse` schemas in `schemas/config.py` to expose `LLM_SKIP_MARGIN_THRESHOLD` and `LLM_SKIP_COVERAGE_THRESHOLD`.
  - Updated `backend/app/api/config.py` to correctly map these new settings from the `ConfigRepository`.
  - Updated frontend `types/api.ts` to match the newly exposed properties.
  - Revamped `frontend/src/app/config.tsx` by adding a dedicated UI section ("LLM Bypass (Fast-Track) Settings") allowing users to modify the margin and coverage thresholds dynamically.
- **Phase 12: UI.md Compliance & Vector Icons Migration**
  - Replaced `@expo/vector-icons` with `lucide-react-native` across all screens and components.
  - Migrated all icon usages to their `lucide-react-native` equivalents (Feather → lucide-react-native icons).
  - Replaced dollar-sign icon with `FontAwesome5` rupee-sign, then transitioned to `lucide-react-native` IndianRupee icon to maintain Indian Rupee branding.

- **Phase 13: Scanned PDF OCR Failure Guard**
  - Fixed "No candidate CV text provided" LLM error caused by scanned PDFs where OCR fails to extract text.
  - Added post-OCR text quality check in `DocumentParser.parse()` to raise `ValueError` when extracted text is just `<!-- image -->` or below a minimum threshold after OCR.
  - Added early validation in `MatchService.analyze_single_cv()` to reject image-only CV text before reaching the LLM, covering reanalysis paths.
- **Phase 14: Processing Timeout Fix**
  - Fixed "Processing timed out" frontend error caused by polling timeout (2 min) shorter than backend processing time (up to 10 min).
  - Removed duplicate LLM call in `background_upload_and_analyze` — `process_cv_file` already does full LLM analysis, so `analyze_from_result_file` was redundant.
  - Updated status endpoint to return `match_analysis` directly from the basic result file (no need for separate `_enriched.json` step).
  - Increased frontend polling limits: `POLL_INTERVAL_MS` 2s→3s, `MAX_POLL_RETRIES` 60→250 (3s × 250 = 12.5 min total).
  - Improved timeout error message to suggest checking candidates list.
- **Phase 16: Pipeline Optimization & LLM Reasoning Reliability**
  - **Eliminated Ollama GPU VRAM Model-Swapping Thrashing**: Removed unused synchronous `EmbeddingService.generate_embedding` call in `process_cv_file` that forced Ollama to constantly unload and re-load GPU model weights (`nomic-embed-text` vs `qwen`).
  - **CV Context Truncation Fix**: Expanded `cleaned_cv` character limit from 3,500 to 7,500 characters in `optimized_match.py`, eliminating context truncation on multi-page resumes that previously caused false "No evidence found" warnings.
  - **Strict Pydantic JSON Schema for Ollama Grammar Enforcement**: Added concrete `ClassifiedRequirementItem` and `RequirementEvidence` sub-models in `analysis.py`, eliminating unconstrained `dict[str, Any]` grammars in Ollama and preventing JSON parsing/validation failures.
  - **Module-Level Thread Pool Reuse**: Replaced thread pool context manager instantiation per document parse with a persistent module-level `ThreadPoolExecutor(max_workers=4)` in `document_parser.py`.
  - **Persistent HTTP Client Sessions**: Added persistent `_get_httpx_client()` session pool in `llm_service.py` to reuse TCP connections across Ollama LLM requests.
  - **8-Stage Execution Profiling**: Updated `PipelineProfiler` and `PipelineStageMetrics` to track and log execution times for all 8 pipeline stages (`upload_ms`, `docling_extraction_ms`, `resume_json_ms`, `db_query_ms`, `cache_lookup_ms`, `prefilter_ms`, `ollama_request_ms`/`model_inference_ms`, `scoring_ms`/`matching_ms`, `total_execution_ms`).

- **Phase 18: Upload Pipeline CACHE MISS & Terminal Status Persistence**
  - **Fixed FileCache Key Path Sanitization**: Sanitized colon namespaces (`cv_result:cv_key.json` → `cv_key.json`) in `FileCache._path()` and `_sanitize_key()`, eliminating duplicate `.json.json` file extension corruption and resolving disk cache lookups returning permanent `CACHE MISS`.
  - **Dual Storage & Disk Persistence**: Guaranteed atomic disk file persistence (`backend/app/uploads/results/<filename>`) in `ResultRepository.atomic_save_result()` regardless of Redis status, and added automatic disk fallback/backfill in `read_result_by_filename()`.
  - **Terminal Failure Persistence**: Wrapped processing in `process_cv_file()` with exception handling that writes a `status: "FAILED"` result JSON containing the specific failure error message on any Docling, OCR, text validation, or LLM error.
  - **Terminal Status Endpoint Handling**: Updated `/api/match/status/{cv_key}` and `/api/cv/status/{cv_key}` to immediately return terminal failure responses (`status: "FAILED"`, `progress: 100`, `message: failure_error`) when processing fails.
- **Phase 20: CV Extraction Redesign & PDF Classification Architecture**
  - **PDF Type Classifier**: Added PyMuPDF (`fitz`) document inspection in `_classify_pdf()` to classify documents into `TEXT_PDF`, `HYBRID_PDF`, or `SCANNED_PDF`.
  - **Primary Docling Extractor**: Designated Docling fast converter (`do_ocr = False`) as the primary extractor for all `TEXT_PDF` and `HYBRID_PDF` documents.
  - **Guarded OCR Decision Logic**: Set OCR decision to `SKIPPED_TEXT_PRESENT` for `TEXT_PDF` and `HYBRID_PDF` documents with valid text. OCR is invoked **only** for `SCANNED_PDF` or when both fast Docling and native text are sparse (< 500 chars).
  - **Non-Fatal OCR Fallback**: Prevented OCR failures or poor outputs from aborting jobs when valid text is extracted by fast Docling or native PyMuPDF.
  - **Stage-Level Execution Tracking**: Added metadata (`pdf_type`, `parser_used`, `ocr_decision`, `stage_metrics`) to `ExtractionResult` and persisted result JSONs.
- **Phase 21: Pipeline Audit & Exception Call Stack Verification**
  - **Code Audit & Search Verification**: Located all occurrences of `raise ValueError`, `RapidOCR`, `_get_ocr_converter`, and document parsing entry points across the codebase.
  - **Execution Path Traceability**: Confirmed complete trace for Upload → Queue → Worker → DocumentParser → Resume Extraction → Matching. Verified single unified pipeline path.
  - **Stale Bytecode Root Cause**: Discovered that the terminal exception (`ValueError: OCR could not extract meaningful text...`) originated from stale in-memory module bytecode in the previously running uvicorn process, which was started before the Phase 20 `document_parser.py` updates were compiled into bytecode.
  - **Architecture Integrity**: Confirmed 0 duplicate `DocumentParser` classes, 0 legacy OCR pipelines, and 1 unified extraction pipeline (`backend/app/services/document_parser.py`).
- **Phase 22: Frontend UI & Candidate Profile Enhancements**
  - **Button Component Upgrade**: Updated `Button.tsx` to support optional vector icon props (`icon?: React.ReactNode`) and clean icon-only button layouts.
  - **Candidate Detail Profile Screen**: Integrated vector `ArrowLeft` navigation and added `HrReviewModal` support into `src/app/candidates/[id].tsx`, enabling HR managers to review and correct candidate scores directly from their candidate profile.
  - **Dashboard Quick Workflows**: Added `Candidate Directory` shortcut row to `src/app/index.tsx` for fast navigation to candidate profiles.
  - **Sidebar & Navigation Sync**: Verified all routes (`/`, `/cv-match`, `/candidates`, `/vacancies`, `/batch`, `/config`) map cleanly in `SidebarLayout.tsx`.
- **Phase 23: Complete API Integration Coverage**
  - **Master Data API Service**: Created `masterDataService.ts` mapping all `/api/master-data/*` endpoints (`getJobProfiles`, `getDepartments`, `getCompanies`, `getSkills`, `warmCache`).
  - **Analytics API Service**: Created `analyticsService.ts` mapping `/api/analytics/cache` and defined `CacheAnalyticsResponse` in `types/api.ts`.
- **pgvector Sidecar - Phase 6: Final Verification & Pipeline Parity**
  - **Full Regression Test Suite Execution**: Validated unit test suite across pgvector cosine similarity, candidate vector persistence, Tarun Gupta pre-filter pipeline, CV idempotency, and document extraction.
  - **Pipeline Parity Confirmed**: Verified `ScoringEngine` remained 100% untouched. Candidate embeddings, vector pre-filtering, and reciprocal rank fusion ($k=60$) function as a non-blocking additive sidecar.

## Files Changed
- `backend/app/services/vacancy_prefilter.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/cv_service.py`
- `backend/app/api/cv.py`
- `backend/tests/test_embedding_similarity.py`
- `backend/tests/test_candidate_embedding.py`
- `backend/tests/test_tarun_gupta_pipeline.py`
- `backend/tests/test_cv_idempotency.py`
- `backend/tests/test_cv_extraction.py`
- `workstatus.md`

## Pending Work
- **pgvector Sidecar Retrieval Pipeline**
  - [x] Phase 0 — Decision Lock
  - [x] Phase 1 — Infrastructure (pgvector container & DB pool)
  - [x] Phase 2 — Schema & migration
  - [x] Phase 3 — Ingestion script & initial population
  - [x] Phase 4 — Candidate-side embedding
  - [x] Phase 5 — Retrieval integration
  - [x] Phase 6 — Verification & parity test






## Important Decisions
- Preserved ScoringEngine, domain word boundary bug fix, and UI styling as untouched isolated items.
- Configured dedicated `pg_engine` and `pg_SessionLocal` in `app/core/database.py` strictly isolated from MSSQL `engine`.
