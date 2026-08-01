# Frontend–Backend Implementation Audit & Gap Analysis

Comprehensive feature parity audit across the entire CV Analyzer application. Every backend API endpoint, service, schema, and data model has been cross-referenced against every frontend page, component, service client, type definition, and UI workflow.

---

## 1. Fully Implemented Features (✅ Complete Parity)

| # | Feature | Backend | Frontend |
|---|---------|---------|----------|
| 1 | **CV File Upload (fast-track)** | `POST /api/cv/upload` | [cvService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/cvService.ts) → [cv-match.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/cv-match.tsx) |
| 2 | **CV File Upload (enriched/LLM)** | `POST /api/match/upload` | [matchService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/matchService.ts) → [cv-match.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/cv-match.tsx) |
| 3 | **CV Status Polling (fast-track)** | `GET /api/cv/status/{cv_key}` | [cvService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/cvService.ts) → [useCvUpload.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/hooks/useCvUpload.ts) |
| 4 | **Match Status Polling (enriched)** | `GET /api/match/status/{cv_key}` | [matchService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/matchService.ts) → [useCvUpload.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/hooks/useCvUpload.ts) |
| 5 | **Raw CV Text Analysis** | `POST /api/match/analyze` | [matchService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/matchService.ts) → [cv-match.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/cv-match.tsx) |
| 6 | **Rule-based CV/Job Match** | `POST /api/cv/match` | [cvService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/cvService.ts) |
| 7 | **LLM Health Check** | `GET /api/match/health` | [matchService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/matchService.ts) → [index.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/index.tsx) (dashboard) |
| 8 | **System Health** | `GET /health` | [index.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/index.tsx) |
| 9 | **Job Listings** | `GET /api/jobs` | [jobsService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/jobsService.ts) → [vacancies/index.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/vacancies/index.tsx) |
| 10 | **Job Detail** | `GET /api/jobs/{job_id}` | [jobsService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/jobsService.ts) → [vacancies/[id].tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/vacancies/%5Bid%5D.tsx) |
| 11 | **Job Cache Invalidation** | `POST /api/jobs/cache/invalidate` | [jobsService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/jobsService.ts) → [vacancies/index.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/vacancies/index.tsx) |
| 12 | **Candidate Search (POST)** | `POST /api/v1/candidates/search` | [candidateService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/candidateService.ts) → [candidates/index.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/index.tsx) |
| 13 | **Candidate List (GET)** | `GET /api/v1/candidates` | [candidateService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/candidateService.ts) → [useCandidates.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/hooks/useCandidates.ts) |
| 14 | **Candidate Detail** | `GET /api/v1/candidates/{id}` | [candidateService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/candidateService.ts) → [candidates/[id].tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/%5Bid%5D.tsx) |
| 15 | **Candidate Reprocess** | `POST /api/v1/candidates/{id}/reprocess` | [candidateService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/candidateService.ts) → [candidates/[id].tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/%5Bid%5D.tsx) |
| 16 | **Match Config (GET/PUT)** | `GET/PUT /api/config/match` | [configService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/configService.ts) → [config.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/config.tsx) |
| 17 | **HR Review Submission** | `POST /api/match/hr-review` | [matchService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/matchService.ts) → [HrReviewModal.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/HrReviewModal.tsx) |
| 18 | **Training Data Retrieval** | `GET /api/match/training-data` | [matchService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/matchService.ts) → [training-data.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/training-data.tsx) |
| 19 | **Batch Candidate Matching** | `POST /api/batch/match-candidates` | [batchService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/batchService.ts) → [batch.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/batch.tsx) |
| 20 | **Batch WebSocket Progress** | `WS /api/batch/ws/progress` | [batchService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/batchService.ts) → [useBatchProgress.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/hooks/useBatchProgress.ts) |
| 21 | **Cache Analytics** | `GET /api/analytics/cache` | [analyticsService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/analyticsService.ts) → [analytics.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/analytics.tsx) |
| 22 | **Performance Metrics** | `GET /api/performance/metrics` | [analyticsService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/analyticsService.ts) → [analytics.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/analytics.tsx) |
| 23 | **Cache Invalidation** | `POST /api/performance/cache/invalidate` | [analyticsService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/analyticsService.ts) → [analytics.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/analytics.tsx) |
| 24 | **Master Data (Profiles/Depts/Companies/Skills)** | `GET /api/master-data/*` | [masterDataService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/masterDataService.ts) |
| 25 | **Cache Warm** | `POST /api/master-data/warm` | [masterDataService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/masterDataService.ts) |
| 26 | **Candidate Recommendations** | `GET /api/recommendations/candidate/{id}` | [candidateService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/candidateService.ts) → [candidates/[id].tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/%5Bid%5D.tsx) |
| 27 | **Vacancy Recommendations** | `GET /api/recommendations/vacancy/{id}` | [jobsService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/jobsService.ts) → [vacancies/[id].tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/vacancies/%5Bid%5D.tsx) |
| 28 | **Per-field Confidence Tiers** | Backend schema fields | [FieldConfidenceView.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/FieldConfidenceView.tsx) across list & detail |
| 29 | **Domain Mismatch Capping Explainability** | `domain_mismatch_capped` / `domain_mismatch_reason` | Badge + banner in candidate list, detail, and MatchAnalysisCard |
| 30 | **Retrieval Source Badges** | `retrieval_source` field | Badge in [MatchAnalysisCard.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/MatchAnalysisCard.tsx) and detail pages |
| 31 | **Mandatory Failure Surfacing** | `mandatory_fails` / `mandatory_failures` | [MatchAnalysisCard.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/MatchAnalysisCard.tsx) & candidate detail |
| 32 | **Similar Candidates (pgvector)** | Computed in `GET /api/v1/candidates/{id}` | [candidates/[id].tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/%5Bid%5D.tsx) |

---

## 2. Backend APIs NOT Integrated in the Frontend

> [!CAUTION]
> These backend endpoints are fully functional but have **zero frontend integration** — no service client, no UI page, no component.

### 🔴 HIGH Priority — Core Functional Gaps

| # | Backend Endpoint | Service | Description | Impact |
|---|-----------------|---------|-------------|--------|
| **G1** | `GET /api/talent-graph/candidate/{id}` | [talent_graph_service.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/talent_graph_service.py) | **Candidate 360 Knowledge Graph** — Returns nodes (Candidate, Skills, Companies, Departments, Vacancies) and edges (HAS_SKILL, WORKED_AT, MATCHED_TO, SIMILAR_TO) for an interactive graph visualization. | No frontend service, type, or page exists. |
| **G2** | `GET /api/talent-graph/vacancy/{id}` | [talent_graph_service.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/talent_graph_service.py) | **Vacancy 360 Knowledge Graph** — Department node, required skills, top candidate matches, similar vacancies. | No frontend integration. |
| **G3** | `GET /api/talent-graph/skill/{skill_name}` | [talent_graph_service.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/talent_graph_service.py) | **Skill Intelligence Graph** — Semantically equivalent skills, candidate supply pool, vacancy demand. | No frontend integration. |
| **G4** | `GET /api/talent-graph/analytics` | [talent_graph_service.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/talent_graph_service.py) | **Recruitment Analytics Graph** — Global node/edge counts, skill frequencies, department distributions. | No frontend integration. |
| **G5** | `GET /api/domain-knowledge/categories` | [domain_knowledge.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/api/domain_knowledge.py) | Lists all 8 supported domain knowledge categories (skills, job_titles, departments, technologies, certifications, education_domains, industries, functional_areas). | No frontend service or page. |
| **G6** | `POST /api/domain-knowledge/equivalents` | [domain_knowledge.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/api/domain_knowledge.py) | **Semantic Term Equivalents** — Resolve semantically similar domain terms for any category with configurable threshold. | No frontend integration. |
| **G7** | `GET /api/vector-db/status` | [vector_db.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/api/vector_db.py) | pgvector connectivity health, table vector counts, model config. | No frontend integration. |
| **G8** | `POST /api/vector-db/sync` | [vector_db.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/api/vector_db.py) | Trigger background sync of all candidate/vacancy embeddings to PostgreSQL pgvector. | No frontend integration. |
| **G9** | `GET /api/recommendations/talent-pools` | [recommendations.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/api/recommendations.py) | **Internal Talent Pools** — Dynamic candidate pools grouped by department, skill cluster, experience tier. | No frontend service call or dedicated page. |
| **G10** | `POST /api/match/reanalyze/{scan_id}` | [analysis.py](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/api/analysis.py) | Re-run LLM semantic matching on a previously parsed CV by scan_id. | Frontend has `matchService.reanalyzeScan()` but **no UI button or trigger** uses it anywhere. |

---

## 3. Partially Implemented Features

> [!WARNING]
> These features have some integration but are missing critical components, data, or functionality.

### 🟡 P1 — Candidate Search: Missing Backend Filters (HIGH Priority)

**Backend** [CandidateSearchRequest](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/schemas/candidate_search.py#L6-L23) supports **10 filter parameters**:
- `query`, `department`, `department_id`, `min_experience`, `max_experience`, `location`, `skills`, `education`, `status`, `limit`, `min_similarity`

**Frontend** [candidates/index.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/index.tsx) only uses:
- `query`, `department` (text), `classification` (client-side filter)

**Missing UI filters:**
- ❌ `min_experience` / `max_experience` range slider or inputs
- ❌ `location` filter input
- ❌ `skills` multi-select filter (backend supports `list[str]`)
- ❌ `education` filter input
- ❌ `status` filter dropdown
- ❌ `min_similarity` threshold slider
- ❌ `department_id` dropdown (from master data departments)

---

### 🟡 P2 — Master Data Not Used for Dropdowns (HIGH Priority)

**Backend** provides master data endpoints:
- `GET /api/master-data/departments` → department list
- `GET /api/master-data/job-profiles` → job profiles
- `GET /api/master-data/companies` → company list
- `GET /api/master-data/skills` → skills list

**Frontend** [masterDataService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/masterDataService.ts) has client functions for all 4 endpoints, but **none are used in any UI component**. Department filters in candidates/vacancies pages are free-text inputs instead of populated dropdowns.

---

### 🟡 P3 — Candidate Detail: Missing Recommendation Fields (MEDIUM Priority)

**Backend** [RecommendationService](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend/app/services/recommendation_service.py) returns:
- `best_vacancies`, `related_skills`, `missing_qualifications`, `recommended_certifications`, `career_transitions`, `talent_pools`, `actionable_suggestions`, `overall_match_confidence`, `hiring_recommendation`, `role_department_fit`, `experience_assessment`, `interview_focus_areas`, `risk_flags`, `next_steps_for_interviewer`, `technical_vs_functional_fit`

**Frontend** [candidates/[id].tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/%5Bid%5D.tsx) renders:
- ✅ `hiring_recommendation`, `experience_assessment`, `role_department_fit`, `risk_flags`, `strengths`, `interview_focus_areas`, `talent_pools`, `related_skills`
- ❌ `missing_qualifications` — Type defined in [api.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/types/api.ts#L418-L423) but **never rendered** in the UI
- ❌ `recommended_certifications` — Not displayed anywhere
- ❌ `best_vacancies` — Not rendered (distinct from best_match; these are recommended openings)
- ❌ `career_transitions` — Not displayed
- ❌ `actionable_suggestions` — Not displayed
- ❌ `next_steps_for_interviewer` — Not displayed
- ❌ `technical_vs_functional_fit` — Not displayed
- ❌ `overall_match_confidence` — Not displayed (distinct from match score)

---

### 🟡 P4 — Vacancy Detail: Missing Data Sections (MEDIUM Priority)

The vacancy detail page at [vacancies/[id].tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/vacancies/%5Bid%5D.tsx) is well structured but missing:
- ❌ **Preferred Gender** display (`preferred_gender` field exists in `JobOpening`)
- ❌ **Domain & Job Family classification** display (`domain`, `job_family` fields)
- ❌ **Similar Vacancies** from `VacancyRecommendationsResponse.similar_candidates`
- ❌ **Vacancy 360 Knowledge Graph** (G2 above)

---

### 🟡 P5 — Candidate Detail: Missing Component Score Visualization (MEDIUM Priority)

The [ComponentScoreBar.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/ComponentScoreBar.tsx) component exists and is imported in [candidates/[id].tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/%5Bid%5D.tsx#L15), but the 8-component score breakdown (`role_score`, `skills_score`, `experience_score`, `education_score`, `domain_score`, `technology_score`, `certification_score`, `responsibilities_score`) is **never rendered** in the candidate detail view.

The backend returns all 8 component scores on every `JobMatchScore`, but the frontend only shows the `overall_score`.

---

### 🟡 P6 — Candidate Detail: Missing MatchAnalysisCard Usage (MEDIUM Priority)

The candidate detail page shows a compact best match card but does **not** use the rich [MatchAnalysisCard.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/components/ui/MatchAnalysisCard.tsx) component (which displays requirement evaluations, matched/missing skills, evidence snippets, component scores). This component is only used in [cv-match.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/cv-match.tsx).

---

### 🟡 P7 — Dashboard: No Candidate Count StatCard (LOW Priority)

The dashboard shows Active Vacancies count but does **not** show total processed candidates count as a StatCard, even though the data is available from the candidates list.

---

### 🟡 P8 — Batch Screen: No Navigation to Candidate Detail (MEDIUM Priority)

The batch result cards in [batch.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/batch.tsx) display `candidate_id` and `candidate_name` but are **not pressable/navigable** to the candidate detail page.

---

## 4. Frontend Functionality Missing Backend Support

> [!NOTE]
> These items have frontend code but the backend data may be mock/hardcoded or incomplete.

| # | Frontend Feature | Status |
|---|-----------------|--------|
| **F1** | `matchService.reanalyzeScan()` | Service client function exists but **no UI trigger** invokes it. Dead code. |
| **F2** | Dashboard "Unreviewed" stat | Counts candidates without `best_match.classification`. This is client-side computed, not a backend stat. Works but is approximation-based. |
| **F3** | Dashboard "OCR Warnings" stat | Client-side filter on `ocr_applied` flag. Works correctly. |
| **F4** | Dashboard "Failed Parses" stat | Client-side filter on `page_count === 0`. This is an approximation (0 pages doesn't always mean failed). |

---

## 5. Missing CRUD Operations

| Resource | Create | Read | Update | Delete |
|----------|--------|------|--------|--------|
| **Candidates** | ✅ Via CV upload | ✅ List + Detail | ✅ Reprocess | ❌ No delete candidate |
| **Vacancies/Jobs** | ❌ No create (read-only from MSSQL DB) | ✅ List + Detail | ❌ No edit | ❌ No close/archive |
| **Training Data** | ✅ Via HR review | ✅ List | ❌ No edit | ❌ No delete |
| **Config** | N/A | ✅ GET | ✅ PUT | N/A |
| **Domain Knowledge** | ❌ | ❌ (backend exists but no frontend) | ❌ | ❌ |
| **Rule Config** | ❌ | ❌ No frontend for `rule_config.json` management | ❌ | ❌ |

---

## 6. Missing Validations, Loading States, Error Handling, and Empty States

| # | Issue | Location | Priority |
|---|-------|----------|----------|
| **V1** | Config page: No input validation (threshold can be set to negative, weights to non-numeric values) | [config.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/config.tsx) | MEDIUM |
| **V2** | Vacancy list: No loading skeleton or shimmer effect (just spinner) | [vacancies/index.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/vacancies/index.tsx) | LOW |
| **V3** | Vacancy detail: `console.warn` on load failure instead of user-facing error | [vacancies/[id].tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/vacancies/%5Bid%5D.tsx#L89-L92) | MEDIUM |
| **V4** | Vacancy detail: Recommendations error silently `console.warn`'d, no error banner | [vacancies/[id].tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/vacancies/%5Bid%5D.tsx#L101-L103) | MEDIUM |
| **V5** | Batch page: No limit validation feedback if user enters invalid limit | [batch.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/batch.tsx) | LOW |
| **V6** | Dashboard: No error state if all API calls fail simultaneously | [index.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/index.tsx) | LOW |

---

## 7. Missing Sorting and Pagination

| # | Issue | Location | Priority |
|---|-------|----------|----------|
| **SP1** | Candidate list: **No pagination** — all candidates loaded at once (limited to `limit=50` default) | [candidates/index.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/index.tsx) | HIGH |
| **SP2** | Candidate list: **No sorting controls** (by name, date, score, department) | [candidates/index.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/candidates/index.tsx) | MEDIUM |
| **SP3** | Vacancy list: **No pagination** — all jobs loaded at once | [vacancies/index.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/vacancies/index.tsx) | MEDIUM |
| **SP4** | Vacancy list: **No sorting controls** (by title, department, experience, CTC) | [vacancies/index.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/vacancies/index.tsx) | MEDIUM |
| **SP5** | Training data: **No pagination** — hardcoded `limit=100` | [training-data.tsx](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/app/training-data.tsx) | LOW |

---

## 8. Inconsistent Data Models

| # | Issue | Backend | Frontend | Priority |
|---|-------|---------|----------|----------|
| **D1** | `CandidateSearchRequest` filters mismatch | Accepts `location`, `skills`, `education`, `status`, `min_similarity`, `department_id` | Frontend only sends `query`, `department`, `limit` | HIGH |
| **D2** | `VacancyRecommendationsResponse` type is incomplete | Backend returns full recommendation object | Frontend type at [api.ts#L451-L459](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/types/api.ts#L451-L459) uses `any[]` for `top_candidate_matches` and `similar_candidates` | MEDIUM |
| **D3** | `CandidateRecommendationsResponse` type is incomplete | Backend returns `career_transitions`, `actionable_suggestions`, `next_steps_for_interviewer`, etc. | Frontend type at [api.ts#L425-L443](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/types/api.ts#L425-L443) is missing `career_transitions`, `actionable_suggestions` fields | MEDIUM |
| **D4** | No types for Talent Graph API responses | Backend returns `nodes[]`, `edges[]`, `candidate_summary`, etc. | No TypeScript types or service functions exist | HIGH |
| **D5** | No types for Domain Knowledge API | Backend returns `DomainEquivalentResponse` | No TypeScript types exist | MEDIUM |
| **D6** | No types for Vector DB API | Backend returns status dict | No TypeScript types exist | LOW |
| **D7** | `masterDataService` uses `any[]` return types | Backend returns typed domain objects | [masterDataService.ts](file:///Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/frontend/src/services/masterDataService.ts) uses raw `any[]` | LOW |

---

## 9. Performance, Caching & API Optimization Opportunities

| # | Opportunity | Priority |
|---|-------------|----------|
| **O1** | **Candidate list should use POST search endpoint** — Currently `useCandidates.ts` calls `GET /api/v1/candidates` which internally constructs a search request. Directly using `POST /api/v1/candidates/search` with all structured filters would be more efficient. | MEDIUM |
| **O2** | **Master data should be cached on the frontend** — Department/skill/company dropdowns should be fetched once and cached, not re-fetched on each navigation. | MEDIUM |
| **O3** | **Dashboard makes 4 concurrent API calls** (health, llm health, jobs, candidates) on every mount. Consider a combined dashboard summary endpoint or frontend caching. | LOW |
| **O4** | **Vacancy list fetches all vacancies** — Backend `GET /api/jobs` returns all active vacancies without pagination support. Backend should add pagination parameters. | MEDIUM |
| **O5** | **No stale-while-revalidate pattern** — Frontend hooks always show loading spinner during refetch rather than showing stale data with a background refresh indicator. | LOW |

---

## 10. Recommended Implementation Order

### 🔴 HIGH Priority — Should Implement First

| # | Item | Estimated Effort | Why HIGH |
|---|------|-----------------|----------|
| **G1-G4** | Talent Knowledge Graph frontend (service + types + visualization page) | Large | 4 backend APIs returning rich graph data are completely unused. Key differentiator for the platform. |
| **P1** | Candidate search: expose all backend filters (experience, location, skills, education, status, similarity) | Medium | Backend supports 10 filters; frontend uses 2. Major search capability gap. |
| **P2** | Master data powered dropdowns for department/skills/location filters | Medium | Master data APIs exist and are wired; UI just uses free-text inputs instead. |
| **SP1** | Candidate list pagination | Medium | Currently limited to 50 results with no way to page through larger datasets. |
| **P5** | Component score breakdown visualization on candidate detail | Small | Component exists (`ComponentScoreBar`), data exists, just needs wiring. |

### 🟡 MEDIUM Priority — Implement Next

| # | Item | Estimated Effort | Why MEDIUM |
|---|------|-----------------|------------|
| **G5-G6** | Domain Knowledge UI (categories browser + semantic equivalents lookup) | Medium | Useful for recruiters to explore term relationships. |
| **G7-G8** | Vector DB status + sync UI on analytics/admin page | Small | Operational visibility for admins. |
| **G9** | Talent Pools dedicated page | Medium | Backend aggregates dynamic pools; no UI to view them. |
| **P3** | Candidate detail: render missing recommendation fields (missing_qualifications, certifications, career_transitions, next_steps) | Small | Data already fetched, just not rendered. |
| **P4** | Vacancy detail: show domain/job_family, preferred_gender, similar vacancies | Small | Fields exist in the data model. |
| **P6** | Use MatchAnalysisCard on candidate detail page for richer match visualization | Small | Component already built, just not used on detail page. |
| **SP2-SP4** | Sorting controls for candidate and vacancy lists | Medium | Improves usability of list views. |
| **V3-V4** | Vacancy detail: proper error banners instead of console.warn | Small | User can't see errors on failed loads. |
| **D2-D3** | Strengthen TypeScript types (replace `any[]` with proper interfaces) | Small | Type safety improvement. |
| **G10** | Wire up reanalyze button in candidate detail for `POST /api/match/reanalyze/{scan_id}` | Small | Service function exists, no UI trigger. |

### 🟢 LOW Priority — Polish Items

| # | Item | Estimated Effort | Why LOW |
|---|------|-----------------|---------|
| **P7** | Dashboard candidate count StatCard | Trivial | Minor cosmetic gap. |
| **P8** | Make batch result cards navigable to candidate detail | Small | Usability improvement. |
| **V1** | Config page input validation | Small | Edge case protection. |
| **V2** | Loading skeleton/shimmer effects | Small | Polish. |
| **SP5** | Training data pagination | Small | Unlikely to exceed 100 records soon. |
| **O2-O5** | Frontend caching and performance optimizations | Medium | Performance tuning. |
| **D6-D7** | Strengthen remaining `any` types | Small | Code quality. |

---

## 11. Summary Statistics

| Category | Count |
|----------|-------|
| Backend API endpoints | **38** (including both HTTP and WebSocket) |
| Frontend pages/routes | **10** |
| Frontend service clients | **10** |
| Frontend hooks | **8** |
| Frontend UI components | **19** |
| **Fully implemented features** | **32** |
| **Backend APIs with zero frontend** | **10** |
| **Partially implemented features** | **8** |
| **Missing filters/sorting/pagination** | **5** |
| **Missing validations/error handling** | **6** |
| **Data model inconsistencies** | **7** |

> [!IMPORTANT]
> The biggest gap is the **Talent Knowledge Graph** system (4 backend endpoints, ~800 lines of service code generating rich node/edge graph data) which has **zero frontend representation**. This represents the most significant unexposed AI capability in the platform.
>
> The second biggest gap is the **candidate search filter set** — the backend accepts 10 structured filters but the frontend only exposes 2 (query + department), leaving experience range, location, skills, education, status, and similarity threshold filters completely inaccessible to recruiters.
