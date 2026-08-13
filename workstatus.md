# Work Status

## Work Completed
1. **2026-08-13 Compact Candidate CV Intelligence Dashboard**:
    - Refactored the candidate detail route into the requested Candidate Summary → Tabs → Compact Sections flow, with a five-second summary for name/latest role, overall match, recommendation, experience, skills match, domain, top strength, and main concern.
    - Replaced the long overview/processing stack with seven always-visible horizontal tabs: Overview, Skills, Experience, Education, Matches, Risks, and CV. The tab bar remains outside the content scroller so it stays available while the selected section scrolls.
    - Added progressive disclosure for skills, employment history, education/certifications, vacancy matches, strengths/risks, AI reasoning, projects/interview focus/suggested roles/talent pools/similar candidates, and extracted CV text; no CV data source or recruiter action was removed.
    - Added responsive two-column recruiter sections on desktop for the overview, education, risks, and CV details, plus responsive vacancy-card grids, while retaining compact single-column mobile presentation and 44px interaction targets.
    - Moved filename, extraction method, page/status data, processing provenance, version fields, calibration profile, RRF score, stage flags, retrieval path/provenance, and taxonomy path into a collapsed Technical Details panel under the CV tab.
    - Added `frontend/src/__tests__/candidateDashboard.test.mjs` to protect the summary fields, seven-tab navigation, expansion controls, desktop layout, collapsed technical metadata, and removal of Processing as a primary recruiter tab.
    - Files changed: `frontend/src/app/candidates/[id].tsx`, `frontend/src/__tests__/candidateDashboard.test.mjs`, and `workstatus.md`.
    - Verification: candidate dashboard contracts passed; compact-density contracts passed; canonical match-status tests passed (16/16); canonical rendering tests passed (5/5); app-source TypeScript passed; Expo web production export completed with all 15 static routes; targeted `git diff --check` passed.
    - Pending work: repository-wide TypeScript still reports the two existing test-fixture cast errors in `candidateReanalysisFlow.test.ts` and `hiringRiskConfig.test.ts`; the existing `candidateDetailGeneric.test.mjs` still fails its backend MATCHED-selection assertion. The repository has no local ESLint executable/config compatible with the temporary ESLint 9 runner, so a clean targeted lint result was unavailable.
    - Important decision: API calls, payloads, candidate normalization, backend scoring, matching, extraction, Ollama integration, re-analysis behavior, and HR review behavior remain unchanged; compactness is implemented only through presentation, responsive composition, tab routing, and local disclosure state.
1. **2026-08-13 Complete Compact Recruiter Frontend Upgrade**:
    - Standardized the Expo SDK 57 / NativeWind frontend around compact density conventions: 12px cards, 8px component gaps, 12px related-section rhythm, 16px major-section rhythm, 18–20px page titles, and responsive controls that retain 44px mobile interaction areas while rendering at 36–40px on wider screens.
    - Extended and adopted the shared `PageHeader` across every non-dashboard route; added leading and metadata composition without changing existing callers, routing, APIs, state, or business logic. The dashboard intentionally retains its compact branded health hero.
    - Reduced the desktop sidebar from 256px to 232px, compacted navigation rows and icons, tightened breadcrumbs, buttons, fields, tabs, stat cards/grids, state banners, empty/loading states, and modal shells, and removed duplicate class-based plus inline grid gaps.
    - Removed component-owned outer margins from shared candidate, score, experience, risk, and progress components so route containers own vertical spacing; compacted every route, including candidate/vacancy directories and details, CV matching, configuration/setup, analytics, batch, knowledge graph, domain explorer, training data, and authentication states.
    - Reduced reviewed large-spacing utility occurrences from 87 to 34 (61%) and removed all 21 occurrences of the intermediate `p-3.5` / `gap-3.5` patterns while preserving intentionally spacious authentication, full-page state, modal-overlay, and upload affordances.
    - Added `frontend/src/__tests__/compactDensity.test.mjs` to protect card padding, page-title scale, responsive touch/control heights, sidebar width, shared grid gaps, and parent-owned spacing.
    - Files changed: `frontend/UI.md`, `frontend/src/constants/theme.ts`, all frontend route files, `frontend/src/components/auth/AuthenticationGate.tsx`, compact shared/domain UI components under `frontend/src/components/ui/`, `frontend/src/__tests__/compactDensity.test.mjs`, and `workstatus.md`.
    - Verification: app-only TypeScript passed; compact-density contracts passed; canonical match-status tests passed (16/16); canonical rendering tests passed (5/5); Expo web production export completed with all 15 static routes; `git diff --check` passed.
    - Pending work: repository-wide TypeScript remains blocked by two pre-existing incompatible test-fixture casts; the legacy `candidateDetailGeneric.test.mjs` still fails its existing MATCHED-selection assertion; ESLint reports the repository's existing React 19 effect/ref and unescaped-entity violations. Interactive breakpoint screenshots could not be captured because the in-app browser control surface was unavailable, but responsive breakpoint contracts compiled and the complete static export succeeded.
    - Important decision: services, hooks, API types/contracts, backend code, Ollama integration, scoring, recommendations, navigation, and state-management behavior remain unchanged; pre-existing business-test and lint failures were not masked or altered as part of the UI-only task.
1. **2026-08-13 Candidate Intelligence Report Final Delivery Audit**:
    - Re-audited the completed Phase 1–3 candidate page against the requested recruiter questions, data ownership, hierarchy, duplicate-information rules, technical-metadata separation, missing-data semantics, and AI-reasoning preservation.
    - Confirmed the recruiter overview now follows Candidate Summary → Skills Match → Experience → Education → Strengths & Risks → Vacancy Analysis → AI Match Explanation → Secondary Information, with administrative metadata isolated in Processing Details.
    - Confirmed the current implementation answers candidate identity, knowledge, employment evidence, vacancy fit, missing requirements, hiring risks, and recommendation rationale without exposing raw engineering metadata in the normal recruiter view.
    - Files changed in this final audit: `workstatus.md` only; no additional application correction was necessary after the Phase 1–3 implementation.
    - Verification: `git diff --check` passed; source audit found raw baseline identity, RRF, stage, retrieval-path, and calibration-version fixtures only in focused exclusion tests or in the separate administrative processing path.
    - Pending work: execute the focused frontend tests, TypeScript check, and responsive visual inspection when repository execution is explicitly authorized.
    - Important decision: the final audit preserves backend scoring and taxonomy ownership, contains no candidate-specific branches, and leaves the centralized Ollama transport architecture untouched.
1. **2026-08-13 Phase 3 Recruiter UI Cleanup and Quality Contracts**:
    - Audited the candidate detail page for repeated fit, recommendation, domain, experience, education, missing-skill, AI-reasoning, and hiring-risk presentation; kept the overall/canonical skills metrics in the summary, per-vacancy scores in vacancy context, and factual details in their dedicated sections.
    - Removed the repeated skills percentage from the detailed Skills card, removed repeated total experience from the timeline card, removed match rationale from the summary header, and suppresses the primary concern from the secondary concerns list when it is identical.
    - Renamed the secondary tab and cards to `Processing Details`, `Technical Details`, and `Debug Information`; humanized the reprocess confirmation so cache JSON, embeddings, score breakdowns, and multi-stage pipeline terminology are no longer shown in the recruiter flow.
    - Added shared recruiter-term humanization for confidence, mandatory gaps, domain alignment/conflict, semantic reasoning, experience gaps, education concerns, and related AI-identified skills without adding candidate-, department-, or domain-specific mappings.
    - Replaced ambiguous zero/negative fallbacks with evidence-aware states such as `Not identified from CV`, `Not enough evidence`, and `Not available in the analysis`; legacy unconfirmed `0 years` defaults no longer appear as factual experience, and an analysis with no recommendation now routes to Manual Review instead of No Strong Match.
    - Kept `llm_reason` and `semantic_reason` intact through normalization and renders both Potential Match and Manual Review explanations under `AI Match Explanation`; raw calibration versions, baseline identities, RRF fields, stage flags, and retrieval paths remain excluded from the normal recruiter presentation.
    - Added focused contracts for complete candidate-summary fields, canonical 80% / 8 matched / 2 missing skill presentation, missing experience/education/domain/skills, humanized metadata, technical-value exclusion, and AI-reasoning survival for Potential Match and Manual Review.
    - Files changed: `frontend/src/app/candidates/[id].tsx`, `frontend/src/components/ui/ExperienceTimelineCard.tsx`, `frontend/src/components/ui/VacancyEnrichmentPanel.tsx`, `frontend/src/utils/candidateDetail.ts`, `frontend/src/utils/candidateDecisionEvidence.ts`, `frontend/src/utils/vacancyEnrichment.ts`, `frontend/src/__tests__/candidateDetailEnrichment.test.ts`, `workstatus.md`.
    - Verification: `git diff --check` passed; the already-running Expo instance completed a fresh web/SSR bundle and logged application startup without a new candidate-page error. Tests, builds, service starts, and restarts were not executed under the repository execution restriction.
    - Pending work: run the focused frontend contract test, TypeScript check, and responsive recruiter-view inspection when execution is explicitly authorized.
    - Important decision: backend metrics, taxonomy, recommendation status, vacancy grouping, and Ollama outputs remain authoritative; Phase 3 changes only presentation, evidence routing, and missing-data semantics.
1. **2026-08-13 Candidate Detail Recruiter-Label UI Error Fix**:
    - Traced the running Expo error to the raw `suitable_job_roles` badge map in `candidates/[id].tsx`, where runtime API values were trusted as strings and used directly as React keys and text labels.
    - Added page-level normalization for suggested roles, interview focus areas, and talent pools so primitive and supported legacy object-shaped values become clean strings, blank/invalid entries are omitted, and duplicate labels are removed before rendering.
    - Replaced the unsafe raw array maps with the normalized display lists without changing the API contract, candidate scoring, recommendation logic, Ollama integration, or the Phase 1/2 information hierarchy.
    - Files changed: `frontend/src/app/candidates/[id].tsx`, `workstatus.md`.
    - Verification: `git diff --check` passed; the already-running Expo instance hot-rebundled successfully and emitted no recurrence of the logged candidate-page error after the change. Per repository instructions, no build, test, server start, or service restart was run.
    - Pending work: none for the reported UI error; focused type-check/test execution remains available when explicitly authorized.
    - Important decision: normalize only at the presentation boundary to preserve backward compatibility with persisted legacy analysis data and avoid inventing candidate information.
1. **2026-08-13 Phase 2 Hiring-Decision Evidence Hierarchy**:
    - Reorganized the candidate overview into the requested sequence: Candidate Summary, Skills Match, Experience, Education, Strengths & Risks, Vacancy Analysis, AI Match Explanation, and Secondary Information.
    - Added a dedicated decision-evidence view model that consumes the backend's canonical vacancy and component scores without recalculating fit, and separates matched skills, missing required skills, and additional CV-extracted candidate skills.
    - Restored factual employment history ahead of interpretation, retained company/designation/date/responsibility evidence, formatted durations as years/months, and moved overlap/gap review indicators after the factual timeline.
    - Preserved distinct degrees from the same institution, added explicit start/end or ongoing date rendering, and shows Education Match or Education Conflict only when supported by structured candidate/vacancy requirement evidence.
    - Limited initial strengths and concerns to four decision-oriented items, prioritizing matched requirements, CV certifications, documented experience, mandatory failures, failed requirements, severity-ranked hiring risks, qualification gaps, experience issues, and required-skill gaps.
    - Rebuilt every vacancy card around recruiter evidence: canonical overall status/score, Skills/Experience/Education scores, deterministic matched evidence, the main supported gap, and the existing HR Review action.
    - Moved all Ollama reasoning out of vacancy evidence and the header into a separately labeled `AI Match Explanation` section with an explicit warning that AI interpretation is not confirmed CV evidence; raw reasoning/property names and retrieval metadata remain hidden.
    - Retained contact details, projects, interview focus, suggested roles, talent pools, similar candidates, extracted CV text, and processing provenance as secondary or Processing Pipeline information.
    - Files changed: `frontend/src/app/candidates/[id].tsx`, `frontend/src/utils/candidateDecisionEvidence.ts`, `frontend/src/utils/candidateDetail.ts`, `frontend/src/components/ui/ExperienceTimelineCard.tsx`, `frontend/src/components/ui/VacancyEnrichmentPanel.tsx`, `frontend/src/__tests__/candidateDetailEnrichment.test.ts`, `workstatus.md`.
    - Pending work: run the focused frontend contract test, TypeScript check, and responsive visual inspection when execution is explicitly authorized and a frontend service is available.
    - Important decision: extracted CV fields and deterministic backend requirement evaluations remain the factual source; Ollama explanations and inferred skills are presented only as clearly qualified interpretation.
1. **2026-08-13 Phase 1 Recruiter 5-Second Candidate Summary**:
    - Audited the running Compose stack and current build state before implementation: API, worker, auxiliary worker, and scheduler images were built nine minutes before the audit; PostgreSQL, Redis, and the primary worker were healthy; the API responded but remained unhealthy because Ollama was offline; no standalone frontend build output or frontend Compose service was present.
    - Audited the live candidate detail/recommendation payload and the complete frontend/backend field path for identity, latest role/company, total and relevant experience, domain/department/family, fit, confidence, recommendation, skills, education conflicts, hiring risks, experience gaps, and Ollama reasoning.
    - Rebuilt the first visible candidate section into a responsive recruiter summary containing candidate identity, latest available role/company, an explicit recommendation and next-review instruction, overall fit, total/relevant experience, skills fit and required-skill coverage, domain/department, Match Confidence, the highest-priority concern, and available AI match rationale.
    - Added deterministic concern prioritization across mandatory failures, failed requirements including education conflicts, severity-ranked hiring risks, recommendation gaps/risks, domain conflicts, experience-gap indicators, missing skills, and low-confidence evidence; absent analysis now reports unavailable instead of implying no concern.
    - Preserved unavailable values as explicit `Not available` states and did not synthesize relevant experience, role, company, domain, or counts. Relevant experience is consumed only when the persisted `dynamic_profile.relevant_experience_years` exists.
    - Humanized recruiter-facing AI metadata: `calibrated_confidence` is shown as `Match Confidence`; initial screening rank is translated to recruiter language; calibration versions, raw RRF/vector/lexical values, retrieval-path names, model identifiers, stage flags, raw requirement IDs, and unknown quality codes are hidden from the recruiter view.
    - Kept processing/version provenance in the Processing Pipeline tab only and renamed AI detail labels to recruiter-facing language while preserving available Ollama reasoning, grounded evidence, and inferred skills.
    - Files changed: `frontend/src/app/candidates/[id].tsx`, `frontend/src/utils/candidateDetail.ts`, `frontend/src/utils/vacancyEnrichment.ts`, `frontend/src/components/ui/VacancyEnrichmentPanel.tsx`, `frontend/src/types/api.ts`, `frontend/src/__tests__/candidateDetailEnrichment.test.ts`, `workstatus.md`.
    - Pending work: run the focused frontend contract test and TypeScript check, and visually inspect the responsive web/mobile layout when execution is explicitly authorized and a frontend service is available.
    - Important decision: no backend, API response, scoring, recommendation, or Ollama transport/generation behavior was changed; the current API does not consistently persist relevant experience, so the summary honestly displays its absence rather than deriving an unsupported value.
1. **2026-08-13 Ollama Health Backpressure Fix**:
    - Made the centralized Ollama operation deadline include both the in-process lock and cross-process file-lock wait, so a 3-second tags/health budget can no longer wait up to the independent 65-second lock timeout before starting.
    - Propagated the same absolute deadline through tags, generation, embedding, and explicit unload requests while retaining the existing centralized client, endpoint selection, retry loop, circuit breaker, and response schemas.
    - Moved root dependency-health checks to parallel worker threads so synchronous Redis, database, prompt, rules, or Ollama probes cannot block the FastAPI event loop and stall candidate status/API requests.
    - Moved the administrator Ollama health probe off the event loop without changing its response contract.
    - Added focused regressions for lock-inclusive tags deadlines and non-blocking root/admin health probes.
    - Per repository instructions, did not run tests/builds, restart containers, or mutate live services/data; static `git diff --check` passed.
1. **2026-08-13 API Runtime Trace Audit (No Fix Applied)**:
    - Reviewed the complete 1,999-line API trace for candidate `cv_1761664401_CandidateCVFileName_13680` and separated candidate-contract behavior from dependency-health failures.
    - Confirmed canonical persistence changed in PostgreSQL, stale Redis content was detected by checksum and rehydrated, and `GET /api/v1/candidates/{id}` returned the RQ-derived `analysis_run_id` and result version `cvjob_e983567ad39b44d3924de9aaff727defb9968171b5b89c2de492d6af5d603d5e-1`.
    - Confirmed `analysis_run_id=not_available candidate=not_available` occurs on `/api/tags` health probes, which have no candidate analysis context, and on legacy candidate records that predate persisted run IDs.
    - Identified a separate runtime incident: Redis health timed out, an Ollama health probe waited 36.2 seconds for the shared transport lock, Docker health took 49.4 seconds, Ollama later became network-unreachable, and the tags circuit opened, producing `/health` 503 responses.
    - Observed 38 status polls (76 access/request log lines), including a 95.2-second request that released into a burst after the dependency stall; this is consistent with contention/backpressure rather than failed canonical persistence.
    - No application code, configuration, build, service, database, cache, or tests were changed or executed; the supplied trace does not contain worker-side generation logs needed to attribute the original stall more narrowly.
1. **2026-08-13 Unscoped Ollama Tags Telemetry Diagnosis (No Fix Applied)**:
    - Confirmed the supplied `operation=tags path=/api/tags` entry comes from `OllamaLLMService.get_status()` during health/model discovery, outside any candidate analysis execution context.
    - Confirmed `analysis_run_id=not_available`, `candidate=not_available`, and `model='not_applicable'` are therefore accurate: tags discovery has no candidate, analysis run, prompt, or requested model.
    - Confirmed the three-second attempt/total deadline and zero retries reflect the dedicated tags policy and do not describe generation timeout behavior.
    - Files changed: `workstatus.md` only.
    - Pending work: inspect the following tags `SUCCESS`, `MODEL_MISSING`, or failure entry only if health readiness is in question.
    - Important decision: no synthetic candidate correlation should be attached to global health checks, and no Ollama transport change is warranted from this informational configuration line.
1. **2026-08-13 End-to-End Re-analysis Contract, Failure Semantics, and Correlation**:
    - Added an end-to-end re-analysis regression that supplies deterministic transport-shaped Ollama output, maps semantic reasoning and inferred skills into the enriched vacancy, atomically updates the canonical candidate, and verifies the re-analysis response, resolver, and candidate-detail GET all return the exact new reasoning.
    - Preserved historical `_enriched`, `_reprocessed`, and `_latest` artifacts as non-canonical records and retained explicit regression coverage that canonical resolution never depends on selecting an enriched filename.
    - Added an injectable, strongly typed frontend re-analysis service function returning `CVUploadResponse` without an `EnrichedCandidateAnalysis` assertion, plus a candidate-page action contract that commits the awaited response immediately and proves fresh reasoning reaches the card presentation without a delayed refetch.
    - Strengthened classification preservation coverage with a score-45 manual-review vacancy carrying `llm_reason` and inferred `HPLC` skill data through normalization unchanged.
    - Defined distinct `LLM_TIMEOUT`, `LLM_UNAVAILABLE`, and `ANALYSIS_INVALID` background failure codes; invalid structured generation now propagates after centralized retries instead of becoming a successful no-match result, while completed no-match remains a normal candidate match outcome.
    - Added `analysis_run_id` correlation using the durable RQ attempt identity for queued processing and generated IDs for synchronous analysis/re-analysis, propagated through queue execution, CV processing, MatchService, Ollama transport, canonical persistence, API DTOs, and frontend candidate contracts.
    - Added structured correlation logs for Ollama attempts, canonical result updates, and candidate API reads, including candidate ID and canonical result version.
    - Forced explicit re-analysis to bypass both the canonical match-result cache read and the prior LLM response cache key so the endpoint genuinely invokes Ollama before replacing current analysis.
    - Files changed: `backend/app/core/analysis_context.py`, `backend/app/api/analysis.py`, `backend/app/api/candidates.py`, `backend/app/api/cv.py`, `backend/app/repositories/result.py`, `backend/app/schemas/analysis.py`, `backend/app/schemas/contracts.py`, `backend/app/schemas/cv.py`, `backend/app/services/cv_service.py`, `backend/app/services/llm_service.py`, `backend/app/services/match_service.py`, `backend/app/services/ollama_transport.py`, `backend/app/services/processing_queue.py`, `backend/tests/test_reanalysis_persistence.py`, `backend/tests/test_phase5_ollama_standardization.py`, `frontend/src/app/candidates/[id].tsx`, `frontend/src/services/matchService.ts`, `frontend/src/types/api.ts`, `frontend/src/utils/candidateReanalysis.ts`, `frontend/src/__tests__/candidateDetailEnrichment.test.ts`, `frontend/src/__tests__/candidateReanalysisFlow.test.ts`, `frontend/src/__tests__/matchServiceReanalysis.test.ts`, `workstatus.md`.
    - Pending work: run the focused backend regressions, frontend contract tests, and frontend type-check when execution is explicitly authorized; tests/builds were not run because repository instructions prohibit execution without explicit authorization.
    - Important decision: `analysis_run_id` is correlation metadata rather than a second result identity; `analysis_version` identifies the analysis currently embedded in the canonical result, `result_generation_id` retains whole-result generation semantics, and only the canonical candidate record owns current analysis.
1. **2026-08-13 Ollama Per-Attempt Timeout and Total Deadline Fix**:
    - Re-audited the centralized Ollama transport and confirmed generation, embeddings, tags, and unload requests continue to use the existing pooled `OllamaTransport` client and retry loop.
    - Separated the existing `OLLAMA_REQUEST_TIMEOUT` per-attempt cap from each operation's total deadline; generation continues to use `OLLAMA_GENERATE_TIMEOUT_SECONDS` as its complete request-plus-backoff budget.
    - Capped every request attempt by both the configured attempt timeout and the remaining total budget, allowing a configured second generation attempt after a full first-attempt timeout when the total deadline permits it.
    - Kept exponential backoff inside the total budget and retained the original typed transport failure when insufficient budget remains instead of replacing it with a misleading retry-backoff timeout.
    - Added structured start, success, timeout/retry, deadline-exhausted, and final-failure telemetry with operation, model, attempt, attempt timeout, total deadline, elapsed time, remaining budget, prompt-token estimate/actual count, context/output limits, status, and exception class.
    - Files changed: `backend/app/services/ollama_transport.py`, `workstatus.md`.
    - Pending work: run the focused Ollama transport reliability tests when execution is explicitly authorized; tests were not run because repository instructions prohibit them without explicit authorization.
    - Important decision: existing settings provide the two required configurable concepts without a configuration-contract change—`OLLAMA_REQUEST_TIMEOUT` is the attempt timeout and `OLLAMA_GENERATE_TIMEOUT_SECONDS` is the total generation deadline; no hardware policy is hardcoded.
1. **2026-08-13 Ollama Vacancy Enrichment Preservation and Rendering Fix**:
    - Audited the complete `EnrichedJobMatchResult` path from backend schema and API JSON through TypeScript contracts, candidate normalization, backend-provided suitable/manual-review grouping, and every candidate-detail vacancy card.
    - Removed frontend eligibility, score, failure, status, and classification recomputation from `normalizeCandidateMatchAnalysis`; normalization now retains the backend grouping, canonical status, best match, recommendation, and original enriched vacancy object identity.
    - Expanded frontend vacancy types for semantic reasoning, inferred skills, semantic boost, calibrated confidence/version, quality flags, retrieval provenance, grounded LLM requirements/evidence, model metadata, and candidate-level processing quality metadata.
    - Added one reusable vacancy enrichment panel and used it for suitable, potential/manual-review/unsuitable, and best-match cards.
    - Rendered `llm_reason` independently from deterministic recommendation text and added presentation for grounded inferred skills, confidence, retrieval metadata, quality flags, and grounded CV/vacancy evidence.
    - Added focused transformation and presentation coverage proving both manual-review and suitable openings retain their original object and Ollama enrichment fields through normalization and card presentation.
    - Files changed: `frontend/src/utils/candidateDetail.ts`, `frontend/src/types/api.ts`, `frontend/src/app/candidates/[id].tsx`, `frontend/src/components/ui/VacancyEnrichmentPanel.tsx`, `frontend/src/components/ui/index.ts`, `frontend/src/utils/vacancyEnrichment.ts`, `frontend/src/__tests__/candidateDetailEnrichment.test.ts`, `workstatus.md`.
    - Pending work: run the focused frontend tests and frontend type-check when execution is explicitly authorized; these commands were not run because repository instructions prohibit them without explicit authorization.
    - Important decision: backend match classification and grouping remain authoritative; the frontend only validates container shape and groups for presentation without acting as a second scoring engine.
1. **2026-08-13 Re-analysis Frontend Contract and State Handling Fix**:
    - Confirmed and retained the actual re-analysis client contract as `Promise<CVUploadResponse>`, matching the complete canonical candidate object returned by the backend.
    - Changed the candidate detail action to apply the awaited canonical response directly to React state, clear prior errors, and reset its loading state through `finally`; no timeout or delayed refetch controls result visibility.
    - Added a dedicated visible re-analysis error state with distinct candidate-not-found, LLM-timeout, LLM-unavailable, invalid-structured-response, network, and general-server presentations.
    - Preserved actionable backend failure categories for re-analysis as HTTP 404, 504, 503, 422, and 500 responses instead of collapsing Ollama failures into a generic server error.
    - Updated the existing upload hook to extract the nested enriched analysis from the canonical candidate response without restoring the obsolete response type.
    - Added focused backend failure-category coverage and frontend error-presentation coverage.
    - Files changed: `backend/app/api/analysis.py`, `backend/tests/test_reanalysis_persistence.py`, `frontend/src/services/matchService.ts`, `frontend/src/app/candidates/[id].tsx`, `frontend/src/hooks/useCvUpload.ts`, `frontend/src/utils/reanalysisError.ts`, `frontend/src/__tests__/reanalysisError.test.ts`, `workstatus.md`.
    - Pending work: run the focused backend/frontend tests and frontend type-check when execution is explicitly authorized; these commands were not run because repository instructions prohibit them without explicit authorization.
    - Important decision: the endpoint remains synchronous and authoritative; error mapping reuses the centralized Ollama exception hierarchy and does not change transport, generation, retry, timeout, cache, or model-selection behavior.
1. **2026-08-13 Re-analysis Canonical Persistence Contract Fix**:
    - Changed successful re-analysis to atomically overwrite the canonical candidate result instead of creating a competing `*_enriched.json` record.
    - Kept `match_analysis` authoritative and synchronized the same `EnrichedCandidateAnalysis` payload into the in-record `enriched_match_analysis` compatibility alias, matching the existing initial-processing producer contract.
    - Excluded legacy `_enriched`, `_reprocessed`, and `_latest` artifacts from scan discovery and candidate-list precedence while leaving explicitly addressed artifacts available for audit access.
    - Updated re-analysis and HR-review APIs to resolve the canonical candidate record directly, removing enriched-file selection logic.
    - Corrected the frontend re-analysis response type to the full canonical candidate record and made the candidate detail page render that returned record immediately.
    - Added focused regression coverage proving POST re-analysis changes old reasoning to new reasoning, the following candidate GET returns the same new reasoning, and only the canonical filename is saved.
    - Files changed: `backend/app/services/match_service.py`, `backend/app/repositories/result.py`, `backend/app/api/analysis.py`, `backend/tests/test_reanalysis_persistence.py`, `frontend/src/services/matchService.ts`, `frontend/src/app/candidates/[id].tsx`, `frontend/src/hooks/useCvUpload.ts`, `workstatus.md`.
    - Pending work: run the focused backend regression test and frontend type-check when execution is explicitly authorized; tests and builds were not run because repository instructions prohibit them without explicit authorization.
    - Important decision: no Ollama client, endpoint, payload, caching, retry, timeout, model-selection, or generation behavior changed; this fix is limited to authoritative post-generation persistence and consumption.
1. **2026-08-13 Ollama Tags Telemetry Clarity Fix**:
    - Audited all application-side Ollama integrations and reconfirmed `/api/generate`, `/api/embed`, `/api/tags`, and unload operations remain centralized in `OllamaTransport`, with generation and embedding callers routed through the existing services.
    - Corrected misleading `/api/tags` configuration telemetry from `model='none'` to `model='not_applicable'`, accurately reflecting that model discovery has no model request payload.
    - Preserved the configured generation model, model-readiness validation, three-second tags deadline, centralized retry count, request payload, response handling, and health API contract.
    - Added focused regression coverage requiring the model-independent tags label and preventing the ambiguous legacy value from returning.
    - Files changed: `backend/app/services/ollama_transport.py`, `backend/tests/test_phase5_ollama_standardization.py`, `workstatus.md`.
    - Pending work: rebuild/recreate the API and worker containers and run the focused Ollama transport test; these actions were not performed because repository instructions require explicit authorization.
    - Important decision: no timeout, retry, model-selection, or health behavior was changed because the supplied entry was successful request telemetry rather than evidence of an operational failure.
1. **2026-08-13 Ollama Tags Log Interpretation (No Fix Applied)**:
    - Confirmed the reported entry is normal request-configuration telemetry for the model-discovery/readiness `GET /api/tags` operation, not an error.
    - Confirmed `model='none'` is expected because the tags request has no model payload, while `timeout_s=3.0` comes from the dedicated `OLLAMA_TAGS_TIMEOUT_SECONDS` setting and zero retries matches the current centralized retry configuration.
    - Files changed: `workstatus.md` only.
    - Pending work: inspect the immediately following `status=SUCCESS`, `status=MODEL_MISSING`, or `status=FALLBACK` entry if Ollama readiness is still in question.
    - Important decision: no Ollama transport, model, timeout, retry, health endpoint, or Docker configuration change is justified by this informational line alone.
1. **2026-08-13 RQ Cron Scheduler Redis Timeout Resilience**:
    - Traced the scheduler exit to `redis.exceptions.TimeoutError` escaping RQ's recurring-job enqueue loop; the existing shutdown wrapper only handled Redis connection failures during deregistration.
    - Extended the existing `ResilientCronScheduler` to tolerate transient Redis connection and timeout errors during recurring enqueue, cron-state persistence, heartbeat, and shutdown deregistration while preserving unexpected exception propagation.
    - Added a five-second retry floor after a Redis failure so an overdue recurring job cannot cause a hot retry loop.
    - Added focused regression coverage for enqueue timeouts, retry pacing, runtime Redis-operation timeouts, and unexpected enqueue failures.
    - Files changed: `backend/start_scheduler.py`, `backend/tests/test_background_sync_jobs.py`, `workstatus.md`.
    - Pending work: rebuild/recreate the scheduler container and run the focused scheduler tests; these actions were not performed because repository instructions require explicit authorization.
    - Important decision: recovery remains inside the existing scheduler process and preserves the current job registrations, queues, intervals, and RQ contracts; no competing Redis client or scheduler implementation was introduced.
1. **2026-08-13 Docker Desktop Duplicate Log Display Diagnosis**:
    - Compared the Docker Desktop unified Logs view with the raw `docker logs` streams for both `cv_analyzer_api` and `cv_analyzer_worker`.
    - Confirmed raw container output records each API request, health check, Ollama operation, and worker pipeline event only once; the application and worker are not executing those operations twice.
    - Identified the duplicate rows as a Docker Desktop unified Logs view/display issue rather than duplicate Python handlers, duplicate Compose services, or duplicate job execution.
    - Files changed: `workstatus.md` only.
    - Pending work: use `docker compose logs`/`docker logs` for authoritative output, or restart/update Docker Desktop if the unified view continues duplicating rows.
    - Important decision: no application logging or Compose change is warranted based on the raw container evidence.
1. **2026-08-13 Migration 027 PostgreSQL Driver Compatibility Fix**:
    - Traced migration 027's `immutabledict is not a sequence` failure to the psycopg driver interpreting the `%` characters in `LIKE '%VACANCY COVERAGE:%'` as parameter markers when the complete trusted SQL file is passed through `exec_driver_sql()`.
    - Replaced the percent-based `LIKE` assertion with the equivalent PostgreSQL `strpos(system_instruction, 'VACANCY COVERAGE:') > 0` predicate.
    - Preserved the prompt-content validation and migration behavior without changing the shared migration runner or previously issued migrations.
    - Files changed: `backend/scripts/migrations/postgres/027_confidence_aware_matching_prompt.sql`, `workstatus.md`.
    - Pending work: rebuild the `migrate-postgres` image, rerun migration 027, and recreate the application containers. These commands were not executed because repository instructions require explicit authorization.
    - Important decision: the failed migration transaction was not recorded as applied, so the corrected version can run normally without checksum repair or rollback.
1. **2026-08-13 Confidence-Aware CV Matching Pipeline Remediation**:
    - Propagated candidate taxonomy confidence, status, and source from dynamic classification/profile resolution into candidate and retrieval contexts.
    - Changed Stage 0 so only high-confidence taxonomy can strictly exclude incompatible vacancies; low-confidence, ambiguous, and unresolved taxonomy now use broad retrieval instead of producing a terminal no-analysis result.
    - Changed semantic Stage 1 from an exclusive Top-N gate into an RRF rank signal, preserving lexical candidates until final Top-K fusion, and stopped zero-score lexical candidates from receiving artificial lexical rank credit.
    - Added privacy-safe exclusion telemetry for Stage 0 taxonomy decisions, Stage 2 RRF Top-K decisions, and deterministic LLM Top-N selection, including taxonomy confidence and semantic contradiction indicators.
    - Gated taxonomy-derived cross-domain caps on the same configured confidence threshold while preserving independently configured software/non-IT evidence guards.
    - Prevented LLM-inferred skills from entering deterministic candidate text, restored dedicated LLM skill provenance, and retained grounded LLM requirements/evidence in separate non-authoritative API lineage fields.
    - Added raw-to-grounded-to-final count telemetry, missing per-vacancy LLM evaluation flags, and reduced calibration confidence when a supplied vacancy is omitted by the model.
    - Added omitted vacancy requirements to the compact optimized prompt input: maximum experience, maximum CTC, mandatory-skill policy, technologies, responsibilities, and description.
    - Tightened the optimized response model and DB readiness schema so core top-level fields plus per-vacancy reason and fit score are required.
    - Added versioned prompt migration 027 for optimized prompt `3.7` / response schema v2 with exact per-vacancy coverage instructions and a reversible down migration.
    - Aligned the structured-generation deadline to 360 seconds and retries to zero across current local runtime files, Settings, the example environment, README, and Compose forwarding.
    - Added/updated focused tests for high- vs low-confidence prefiltering, ambiguous cross-family survival, non-exclusive vector retrieval, confidence-aware cross-domain guards, LLM provenance, evidence preservation, missing vacancy coverage, strict response validation, prompt completeness/readiness, and configuration parity.
    - Files changed: `README.md`, `backend/.env.example`, local `.env` files, matching/taxonomy/prompt/schema services, migrations 027 up/down, and focused backend tests; `workstatus.md` updated here.
    - Pending work: migration 027 must be applied before processing so prompt 3.7 becomes active. Tests, migrations, builds, and services were not executed because repository instructions prohibit them unless explicitly requested.
    - Important decision: deterministic evaluators remain authoritative; grounded LLM requirement/evidence output is retained as separate lineage and semantic enrichment, never used to override mandatory deterministic failures.
1. **2026-08-13 Existing Ollama Remediation Verification**:
    - Re-audited every application Ollama HTTP path and confirmed generation, tags, embeddings, and unload remain centralized in `OllamaTransport`, with callers routed through `OllamaLLMService` or `EmbeddingService`.
    - Confirmed model-unavailable, timeout, service-unavailable, and retryable HTTP generation failures propagate to the API's `503`/`504` handling; disabled generation and non-operational response failures retain their intended deterministic fallback behavior.
    - Confirmed optimized matching uses the dedicated `OLLAMA_OPTIMIZED_NUM_CTX=8192` and `OLLAMA_OPTIMIZED_NUM_PREDICT=3072` limits.
    - Confirmed `llama3.2:3b` is aligned across the application default, example environment, and README, while base Compose enables LLM generation by default and local Compose does not override it.
    - Ran an AST audit over 34 application-side Ollama error constructions; every construction supplies the required `operation` keyword.
    - Corrected stale Llama test expectations so non-thinking models omit the unsupported `think` payload field, retained Qwen native-thinking coverage, renamed the stale default-model test, and added the missing `OllamaError` import required by the work-experience error-contract test.
    - Ran the complete maintained Ollama standardization, payload, and Compose configuration test files: 53 tests passed with 2 unrelated Redis `setex` deprecation warnings.
    - Files changed: `backend/tests/test_qwen_llm_service.py`, `backend/tests/test_phase5_ollama_standardization.py`, `workstatus.md`.
    - Pending work: none; no application, API, schema, caching, retry, embedding, Compose, or runtime configuration change was required.
    - Important decision: the reported findings refer to an older revision; verification preserves the existing centralized architecture and only repairs the stale test contract.
1. **2026-08-13 Nullable Primary Department Response Compatibility Fix**:
    - Traced `GET /api/cv/status/{cv_key}` failures to completed results containing the valid no-department state `match_analysis.primary_department=null` while the nested response schema required a string.
    - Aligned `CandidateMatchAnalysis.primary_department` with `EnrichedCandidateAnalysis` and the no-active-vacancy producer by making the field nullable with a `None` default.
    - Preserved the response field and its meaning instead of fabricating an empty or fallback department during status serialization.
    - Aligned frontend candidate-analysis contracts with the backend's nullable department and professional-domain fields; existing UI fallbacks already handle absent values.
    - Added focused regression coverage proving a completed `CVUploadResponse` accepts a nested analysis with no primary department.
    - Pending work: tests and services were not run because repository instructions prohibit them unless explicitly requested.
    - Important decision: absence of a department is modeled as `null`; existing string-valued responses remain unchanged.
1. **2026-08-13 Active Ollama Model Configuration Realignment**:
    - Traced the dashboard `CONFIG ERROR — Missing: qwen3:4b` to repository-root and backend-local environment overrides that disagreed with the centralized `llama3.2:3b` default.
    - Confirmed the live Ollama inventory contains `llama3.2:3b`, `gemma3:1b`, and `nomic-embed-text:latest`, but not `qwen3:4b`.
    - Aligned `.env` and `backend/.env` to the installed generation model `llama3.2:3b`; the example environment and Python default were already correct.
    - Pending work: running API and worker processes were not restarted because repository instructions prohibit running services unless explicitly requested.
    - Important decision: configuration was aligned to the existing installed model; no model download, hardcoded service override, or frontend suppression was introduced.
1. **2026-08-13 Frontend Ollama Health Diagnostics Parity**:
    - Updated the dashboard to present reachable Ollama configuration failures separately from server/network outages instead of collapsing both into an offline state.
    - Added explicit configured generation and optional embedding model availability, missing-model guidance, and the installed model inventory returned by the centralized health endpoint.
    - Centralized frontend Ollama health presentation in a small pure utility and added focused regression coverage for configuration-error, offline, and disabled states.
    - Confirmed direct text analysis and queued CV processing already surface backend failure messages through their existing error paths, so no duplicate Ollama-specific frontend client was introduced.
    - Pending work: frontend tests, lint, type-check, build, and services were not executed because repository instructions prohibit them unless explicitly requested.
    - Important decision: a reachable but misconfigured Ollama instance is displayed as `CONFIG ERROR`, while `OFFLINE` is reserved for an unreachable health endpoint.
1. **2026-08-13 Ollama Configured-Model Health Readiness Fix**:
    - Changed `OllamaLLMService.get_status()` readiness from simple `/api/tags` reachability to validation of every enabled configured generation and embedding model.
    - Reused centralized exact canonical model matching, including `:latest` equivalence, without adding another discovery request or health client.
    - Made the LLM health endpoint distinguish a reachable but misconfigured Ollama instance from an unreachable server and report missing model names plus per-model availability.
    - Extended the frontend health response type with optional embedding and missing-model diagnostics while preserving existing fields.
    - Preserved the existing `(ready, installed_models)` service contract so startup verification and model inventory continue using the same centralized tags result.
    - Added focused regression coverage for full readiness, missing generation models, canonical embedding aliases, diagnostic logging, and health response classification.
    - Pending work: focused tests were not executed because repository instructions prohibit running tests unless explicitly requested.
    - Important decision: a reachable Ollama server is not considered application-ready unless every enabled configured model is installed.
1. **2026-08-13 Work Experience Ollama Error Construction Fix**:
    - Fixed the empty work-experience generation path to construct `OllamaError` with the required `operation="work_experience_extraction"` context.
    - Prevented the intended typed service failure from being replaced by a keyword-argument `TypeError`.
    - Added focused asynchronous regression coverage for the exception type, message, operation, and retryability contract.
    - Pending work: the focused test was not executed because repository instructions prohibit running tests unless explicitly requested.
    - Important decision: the existing public service contract and retryable default were preserved; only the defective exception construction changed.
1. **2026-08-13 Ollama Infrastructure Error Propagation Fix**:
    - Centralized the higher-level operational-failure policy for timeouts, connection/unavailability errors, circuit/concurrency failures through their typed parents, missing models, and retry-exhausted retryable HTTP responses.
    - Changed structured generation to trace and re-raise those failures instead of returning `None`, while retaining deterministic fallback for malformed JSON and schema-invalid response content.
    - Allowed propagated `OllamaError` failures through Hiring Risk and preliminary/enriched matching catches so infrastructure outages cannot become partial analysis.
    - Mapped timeout/concurrency failures to HTTP 504 and other operational Ollama failures to HTTP 503 at the synchronous analysis boundary.
    - Added focused regression coverage for timeout, connection, retryable HTTP, Hiring Risk, trace classification, and API status mapping behavior.
    - Pending work: focused tests were not executed because repository instructions prohibit running tests unless explicitly requested.
    - Important decision: transport handling and retry behavior remain unchanged; only post-transport propagation was corrected.
1. **2026-08-13 Local Compose LLM Enablement Fix**:
    - Removed the local Compose `LLM_ENABLED=false` fallback so the Apple Silicon profile inherits the base Compose default of enabled generation.
    - Preserved `EMBEDDING_ENABLED=false` in the constrained local profile because vector generation is an independent opt-in feature.
    - Updated local-profile documentation to state that generation is enabled by default and can still be explicitly disabled with `LLM_ENABLED=false`.
    - Added focused regression coverage requiring the base enabled default, absence of a local `LLM_ENABLED` override, and preservation of the local embedding default.
    - Pending work: Compose rendering, tests, builds, and container recreation were not executed because repository instructions prohibit those actions unless explicitly requested.
    - Important decision: the local profile now inherits the base generation switch instead of maintaining a competing default.
1. **2026-08-13 Ollama Missing-Model Error Propagation Fix**:
    - Changed structured generation so `OllamaModelUnavailableError` is logged with complete typed context, traced as a propagated failure, and re-raised instead of being converted to `None`.
    - Preserved the existing deterministic `None` fallback for other recoverable Ollama, invalid JSON, and schema failures.
    - Prevented Hiring Risk enrichment and both preliminary and enriched per-vacancy matching loops from catching and suppressing the propagated missing-model configuration error.
    - Mapped the propagated error to an explicit HTTP 503 on synchronous CV analysis instead of a generic 500 or partial response.
    - Added focused regression coverage proving missing generation models retain their 404, retryability, detail, trace, and exception identity through higher-level services and become a safe API-level 503.
    - Pending work: focused tests were not executed because repository instructions prohibit running tests unless explicitly requested.
    - Important decision: only the typed missing-model failure is fail-fast; existing recoverable fallback contracts remain unchanged.
1. **2026-08-13 Ollama Generation Model Alignment to Qwen 3 4B**:
    - Audited all generation model sources and found the Python default, checked-in backend environment template, repository-root Docker environment, backend-local environment, documentation, and payload expectations were not aligned with the installed `llama3.2:3b` model.
    - Set `llama3.2:3b` in the centralized `Settings.OLLAMA_MODEL` default, `backend/.env.example`, repository-root `.env`, and backend-local `.env`.
    - Kept `docker-compose.yml` unchanged so Compose continues requiring and forwarding the repository-root `OLLAMA_MODEL` value without another fallback.
    - Updated maintained documentation and default-model payload expectations, including native Qwen 3 `think` behavior for thinking and non-thinking operations.
    - Pending work: running API and worker containers were not recreated, and tests were not executed because repository instructions prohibit those actions unless explicitly requested.
    - Important decision: no model name was added outside configuration surfaces or tests; application services continue reading `settings.OLLAMA_MODEL`.
1. **2026-08-13 Ollama Non-Streaming Response Contract Lock**:
    - Confirmed every maintained generation payload sets `stream=false` and the synchronous transport uses `response.iter_bytes()` only to bound and accumulate the HTTP body.
    - Added regression coverage in which one valid Ollama JSON envelope is fragmented across four HTTP chunks and successfully decoded only after the full body is joined.
    - Preserved single-object `json.loads()` parsing; no NDJSON, line-by-line parsing, or token-streaming path was introduced.
    - Changed only the focused Ollama transport test and this work-status record; production response parsing was already correct.
    - Pending work: the regression test was not executed because repository instructions prohibit running tests unless explicitly requested.
1. **2026-08-13 Ollama Generate Endpoint Contract Lock**:
    - Confirmed prompt-oriented generation remains centralized on `POST /api/generate`; no `/api/chat` path exists in backend application code.
    - Added focused regression coverage for the exact HTTP method and endpoint plus the `model`, `prompt`, `format`, `stream`, `think`, `keep_alive`, and `options` payload contract.
    - Changed only the focused Ollama transport test and this work-status record; production behavior required no change because it was already correct.
    - Pending work: the regression test was not executed because repository instructions prohibit running tests unless explicitly requested.
    - Important decision: `/api/chat` is not appropriate for the repository's prompt-oriented generation flow and was not introduced.
1. **2026-08-13 Surgical Ollama Transport Hardening**:
    - Preserved the single `OllamaTransport` integration for `/api/generate`, `/api/embed`, `/api/tags`, payload construction, pooled HTTP access, retries, and timeouts.
    - Added fail-fast validation for the Ollama base URL, enabled model names, timeout/retry bounds, connection/response limits, circuit-breaker and embedding limits, and generation token budgets.
    - Standardized operation, retryability, status code, and sanitized detail fields across transport exceptions, and added endpoint/model context to transport failure logs.
    - Centralized exact canonical model-name matching, including `:latest` equivalence, and reused it in startup verification and the health response instead of substring matching.
    - Fixed production startup verification so an unavailable configured model raises instead of being caught and downgraded to a warning.
    - Defensively rejected unload or other non-generation completion reasons before a generation response reaches higher-level parsing.
    - Added focused regression coverage for invalid configuration, canonical model matching, production model availability, typed timeout context, and invalid generation completion reasons.
    - Pending work: focused tests were added but not executed because repository instructions prohibit running tests unless explicitly requested.
    - Important decision: no new Ollama client, SDK, endpoint wrapper, payload builder, model source, or embedding path was introduced.
1. **2026-08-13 Legacy Mandatory-Failure Response Compatibility Fix**:
    - Traced the `POST /api/match/upload` 500 to completed cached analysis records created before `MandatoryFailureDetails.failure_code` became required.
    - Added centralized schema hydration that preserves current explicit codes and derives the current evaluator code for legacy skill, experience, certification, CTC, and domain failures.
    - Assigned unknown historical requirement types the neutral `LEGACY_MANDATORY_FAILURE` identity instead of rejecting the entire completed response or inventing a specific risk category.
    - Added focused regression coverage for the logged minimum-experience payload, nested best/unsuitable openings, current-code preservation, every supported legacy mapping, and the neutral fallback.
    - Per repository instructions, did not run backend tests, builds, migrations, or services.
1. **2026-08-13 Default Hiring Risk Prompt and Identity**:
    - Added a centralized built-in `hiring_risk_explanation` prompt fallback in `PromptService`, using version `default-1.0.0` and a stable SHA-256 content identity.
    - Kept active PostgreSQL prompt records authoritative; the built-in default is used only when no compatible active record exists or database prompt lookup is unavailable.
    - Updated unversioned and versioned prompt resolution plus provenance lookup so runtime generation, CV persistence, match-cache identities, and candidate detail metadata all resolve the same default.
    - Made stale cached `__MISSING__` version/identity markers resolve to the built-in default instead of continuing to emit `missing` until cache expiry.
    - Reused the centralized default template from the maintained prompt seeder and aligned `HiringRiskAnalyzer.PROMPT_NAME` with the same centralized constant.
    - Replaced literal `missing` values on legacy candidate-detail provenance with honest default-availability messages; the UI directs reprocessing before claiming the default version or identity was historically recorded.
    - Added focused regression coverage for default prompt content, version, identity, cached-missing recovery, and analyzer prompt-name alignment.
    - Per repository instructions, did not run backend tests, builds, migrations, or services.
1. **2026-08-13 Candidate Detail Card Visibility Fix**:
    - Traced invisible candidate-detail cards to conditional rendering that omitted Hiring Risks for empty arrays, omitted processing provenance for legacy records, and provided no explanation when canonical fit metadata was absent.
    - Made the top vacancy's Hiring Risks card visible with an explicit no-active-risk state when no deterministic policy fires, while preserving omission for non-top matches without risks.
    - Made Processing Provenance visible on both the default Overview tab and Processing Pipeline tab; legacy results now show every version field as `Not recorded` with a reprocessing explanation.
    - Added a canonical-fit unavailable state for stored results that predate hierarchy score-breakdown metadata.
    - Extracted processing provenance normalization into a reusable utility and added regression coverage for legacy and current result payloads.
    - Per repository instructions, did not run frontend tests, lint, type-check, build, or services.
1. **2026-08-13 Frontend Parity for Today's Backend Implementations**:
    - Added explicit frontend contracts for versioned hiring-risk policies and backend processing provenance.
    - Extended the active Engine Configuration screen to create, edit, enable/disable, classify, require manual review for, and remove hiring-risk policies through the existing full-profile version creation and activation workflow.
    - Expanded Hiring Risks cards with severity, category, stable risk code, deterministic source, deduplicated evidence, and complete styling for `LOW` and `UNKNOWN` severities.
    - Added a distinct informational state for unavailable hierarchy validation while preserving the backend rule that only an explicit mismatch rejects or penalizes a match.
    - Added an administrator-facing Processing Provenance card for matching, rule configuration, hiring-risk policy/prompt, optimized prompt, and LLM model versions.
    - Added focused source-level regression tests for policy preservation, risk evidence presentation, and all hierarchy-validation states.
    - Reviewed the Expo SDK 57 reference before implementation; no new SDK dependency or platform API was required.
    - Per repository instructions, did not run frontend tests, lint, type-check, build, or services.
1. **2026-08-13 Frontend Gap Audit for Today's Backend Implementations**:
    - Compared today's hiring-risk policy, hierarchy tri-state, recommendation, optimized-match, Ollama transport, migration, and worker-identity changes with the frontend types, services, configuration screens, candidate detail views, and focused frontend tests.
    - Confirmed the recommendation nullability fix, optimized-match budget/telemetry, Ollama response handling, migration execution, and RQ worker identity changes do not require frontend contract changes.
    - Identified the missing active-profile editor and explicit frontend types for versioned hiring-risk policies, incomplete risk evidence/category/source presentation, missing processing-version metadata presentation, and missing visual treatment/test coverage for unknown hierarchy validation.
    - Kept the audit diagnostic-only; no frontend application code, tests, builds, or services were changed or executed.
1. **2026-08-13 Docker Ollama Model Alignment to Llama 3.2**:
    - Confirmed the newly installed local generation model is `llama3.2:3b` while the running API and worker containers still use `gemma3:1b`.
    - Updated the repository-root `.env`, the single Docker model source, to `OLLAMA_MODEL=llama3.2:3b`.
    - Confirmed the application default and environment template already use `llama3.2:3b`; no duplicate model setting was introduced.
    - Did not recreate containers, so the running API and worker remain on `gemma3:1b` until deployment is authorized.
1. **2026-08-13 Nullable Canonical Experience Recommendation Fix**:
    - Traced the `/api/recommendations/candidate/cv_1764311881` failure to `RecommendationService` converting the canonical unknown experience duration (`None`) with `float(None)`.
    - Preserved the canonical experience engine's four-state contract instead of coercing unknown duration to zero.
    - Limited the low-experience risk flag to known numeric durations so documented employment with unavailable dates is not mislabeled as limited experience.
    - Added focused regression coverage for recommendations with documented employment and unparseable dates.
    - Per repository instructions, did not rebuild, restart, or test services.
1. **2026-08-13 Optimized Match Output Budget Fix**:
    - Confirmed `optimized_match` explicitly requested 2,048 output tokens but shared the 4,096-token general context window, leaving only about 1,677 tokens after the observed 2,419-token prompt.
    - Added a dedicated 8,192-token optimized-match context and raised its explicit output allowance to 3,072 tokens, leaving about 2,701 tokens of additional headroom for prompt framing and schema overhead at the observed prompt size.
    - Added centralized success and truncation telemetry for response characters, actual output tokens, `num_predict`, and `num_ctx`.
    - Made output-limit failures non-retryable because repeating an identical deterministic request with unchanged limits cannot complete the response.
    - Added configuration validation and focused payload/retry regression coverage.
    - Ran the two explicitly requested focused regression tests: 2 passed with 2 unrelated Redis-client deprecation warnings; did not build, start, or restart services or run the full suite.
1. **2026-08-13 Vacancy Hierarchy Tri-State Validation Fix**:
    - Traced repeated vacancy matching failures to `HierarchyClassificationResult.is_hierarchy_valid=None` being passed into a score-breakdown schema that accepted only booleans.
    - Aligned the vacancy-fit response schema and frontend API type with the existing tri-state hierarchy contract: `true` is valid, `false` is invalid, and `null` means validation was unavailable.
    - Preserved scoring behavior so only an explicit `false` triggers hierarchy rejection; an unknown value remains eligible for the other deterministic gates.
    - Added focused regression coverage for preserving the unknown hierarchy-validation state.
    - Per repository instructions, did not build, run, restart, or test services.
1. **2026-08-13 RQ Worker Registration Collision Fix**:
    - Traced the auxiliary-worker restart loop to the fixed `cv-analyzer-auxiliary-worker` name colliding with an existing active/stale Redis registration.
    - Added a shared collision-resistant RQ identity builder that retains stable role prefixes and appends a per-process UUID.
    - Applied unique identities consistently to auxiliary and primary CV workers, eliminating the same latent restart collision without deleting Redis workers, queues, or jobs.
    - Added worker startup logging for the resolved identity and focused tests for worker wiring, stable prefixes, uniqueness, and invalid roles.
    - Per repository instructions, did not build, run, restart, or test services.
1. **2026-08-13 PostgreSQL Migration JSON Bind-Parsing Fix**:
    - Diagnosed migration 025 failure as SQLAlchemy `text()` interpreting JSON tokens such as `:true` and `:false` as bind parameters.
    - Added one raw-driver migration execution helper for trusted repository SQL files and routed both forward and rollback scripts through it.
    - Preserved parameterized SQLAlchemy execution for migration-history queries and writes.
    - Kept migration 025 unchanged; its failed transaction was not recorded as applied and can be retried after rebuilding the migration image.
    - Added focused regression coverage proving JSON literals are passed unchanged without bind-parameter parsing.
    - Per repository instructions, did not rerun migrations, tests, builds, or services.
1. **2026-08-13 Ollama Response Integrity Remediation**:
    - Removed Qwen-specific thinking directives from maintained prompt seeds and removed the obsolete duplicate optimized prompt from the generic seeder while preserving the checksum of already-issued migration 024.
    - Added versioned PostgreSQL migration 026 to activate model-neutral optimized prompt version `3.6`, remove legacy directives from generic prompts, and invalidate version-bound caches safely.
    - Added centralized defensive removal of legacy first-line thinking directives and prompt-readiness rejection for incompatible active optimized prompts.
    - Versioned the optimized prompt cache key so persisted `3.5` cache entries cannot shadow the corrected `3.6` database prompt.
    - Preserved bounded, whitespace-normalized Ollama error details for HTTP and JSON error envelopes and included status, retryability, and safe detail in transport/generation fallback logs.
    - Added explicit deterministic-fallback and embedding-throttle logging so missing LLM/embedding results no longer disappear silently.
    - Aligned Docker and local generation deadlines at 90 seconds and made the Docker request/generation timeout values required root-environment inputs.
    - Added focused regression coverage for sanitized server detail, JSON error envelopes, legacy prompt normalization, prompt readiness, native thinking-model behavior, and throttle observability.
    - Per repository instructions, did not run tests, builds, migrations, or services.
1. **2026-08-13 End-to-End Ollama Response Audit (No Fix Applied)**:
    - Confirmed all Ollama HTTP traffic is centralized in `OllamaTransport`: generation and unload use `/api/generate`, embeddings use `/api/embed`, and discovery uses `/api/tags`.
    - Confirmed generation sends `stream=false`, reads the complete response body, and parses one JSON object; a live local request using the repository payload shape returned the expected non-streaming envelope and structured JSON response.
    - Confirmed the configured generation model `llama3.2:3b` and embedding model `nomic-embed-text` match the locally installed `llama3.2:3b` and `nomic-embed-text:latest` models.
    - Found the versioned optimized-match PostgreSQL prompt migration still stores a leading `/think` directive, so the active Gemma request can retain Qwen-specific prompt content despite transport-level capability handling.
    - Found HTTP and JSON error handling discards Ollama's diagnostic error body, logs only exception class names, then converts generation failure to `None`; optimized matching consequently continues without an LLM result.
    - Found embedding connection/model failures activate a 60-second model throttle whose subsequent early returns are not logged.
    - No application code, migrations, database state, builds, tests, or services were changed or executed; only read-only source, local model inventory, and one minimal local generation request were used.
1. **2026-08-13 Gemma 3 Ollama Generation Compatibility Fix**:
    - Centralized thinking-capability resolution in `OllamaLLMService` for recognized thinking model families.
    - Removed Qwen-specific `/think` and `/no_think` prompt prefixes from the shared structured-generation path.
    - Changed the centralized generation payload builder to omit `think` for Gemma 3 and other non-thinking models while preserving native `think` requests for supported models.
    - Kept `/api/generate`, `/api/embed`, model selection, retries, caching, timeouts, and response contracts unchanged.
    - Updated focused payload tests for `llama3.2:3b` and added coverage ensuring a Qwen 3 model retains the native thinking parameter.
    - Per repository instructions, did not run tests, builds, services, or migrations.
1. **2026-08-13 Docker Ollama Model Source Consolidation**:
    - Set the repository-root Docker environment override to `OLLAMA_MODEL=llama3.2:3b`.
    - Changed `docker-compose.yml` to require `OLLAMA_MODEL` from the repository-root environment instead of maintaining a second fallback value.
    - Removed the competing `qwen3:1.7b` declaration from `docker-compose.local.yml`; local Compose now inherits the required base environment value.
    - Updated local-profile documentation to use the inherited model instead of supplying another command-line model override.
    - Confirmed application integrations continue consuming the resolved model through `app.core.config.settings`.
    - Per repository instructions, did not build, test, start, or recreate Docker services.
1. **2026-08-13 Docker Ollama Model Configuration Check (No Fix Applied)**:
    - Confirmed the centralized application default, primary Compose fallback, backend example environment, README, and current backend-local environment use `llama3.2:3b`.
    - Found the repository-root `.env` still sets `OLLAMA_MODEL=gemma3:4b`; Docker Compose interpolation therefore overrides the `llama3.2:3b` fallback in `docker-compose.yml`.
    - Found `docker-compose.local.yml` still has a `qwen3:1.7b` fallback, although the current root `.env` value takes precedence when that override is used.
    - No Docker services, builds, tests, or application configuration files were changed or executed.
1. **2026-08-13 Backend/Test Dead-Artifact Cleanup**:
    - Audited tracked and untracked files under `backend/` and `backend/tests/` against Python imports, dynamic path loading, Docker/Compose, CI, migrations, documentation, and tests.
    - Removed unreferenced root-level scratch probes, hardcoded candidate/vacancy diagnostics, source-rewriting patch helpers, one-off cache/database commands, a generated audit log, and a print-only debug test.
    - Moved three assertion-based root tests into `backend/tests/` instead of deleting their coverage: education requirement matching, relevant experience, and score ownership.
    - Preserved runtime entry points, maintained operational scripts, all PostgreSQL migrations, `uv.lock`, `department_domains_seed.json`, and `tests/mock_rule_config.py`.
    - Verified no remaining repository reference names a removed artifact and `git diff --check` passes.
    - Ran the complete backend suite: 571 tests passed and 106 failed. Collection and execution complete without deleted-module/import failures; existing functional failures remain across taxonomy, extraction, scoring, configuration, and Hiring Risks behavior.
    - Ran Ruff across application, tests, entry points, and scripts; it reports 362 pre-existing lint findings (308 auto-fixable), so no unrelated bulk formatting was applied.
1. **2026-08-13 Scratch File Removal — lexical/plant diagnostics**:
    - Removed `backend/test_lexical_1215.py`, which duplicated lexical scoring for fixed candidate/vacancy IDs and executed live database work during pytest import.
    - Removed `backend/check_plant_exp.py`, an unreferenced module-level database inspection hardcoded to `Plant Assistant - I`.
    - Reconfirmed `backend/requirements.txt` and `backend/workstatus.md` remain removed while `backend/uv.lock` and `backend/app/data/department_domains_seed.json` remain present.
1. **2026-08-13 Scratch File Removal — `test_top10.py`**:
    - Removed the tracked candidate-specific top-10 ranking experiment that ran live PostgreSQL, embedding, and vacancy-prefilter operations during module import.
    - Confirmed it had no assertions or repository consumers; maintained `top_k=10` coverage remains in `backend/tests/test_vacancy_prefilter.py`.
1. **2026-08-13 Scratch File Removal — `test_rrf_rank.py`**:
    - Removed the tracked candidate/vacancy-specific RRF diagnostic that performed live PostgreSQL, embedding, pgvector, and vacancy-prefilter operations during module import.
    - Confirmed it had no assertions or repository consumers and overlapped maintained ranking/prefilter coverage under `backend/tests/`.
1. **2026-08-13 Scratch File Removal — `test_candidate_1760668444.py`**:
    - Removed the tracked candidate-specific diagnostic that queried PostgreSQL and ran `MatchService.analyze_single_cv()` at module import through `asyncio.run()`.
    - Confirmed it had no assertions, reusable pytest tests, or repository consumers; other candidate-specific scripts were left unchanged pending individual review.
1. **2026-08-13 `test_unknown_fallback.py` Removal Verification**:
    - Reconfirmed `backend/test_unknown_fallback.py` is absent, has no remaining repository references, and can no longer be imported by pytest discovery.
1. **2026-08-13 Repository Artifact Cleanup — Phases 2–4**:
    - Removed the redundant generated `backend/requirements.txt`; `backend/pyproject.toml` and `backend/uv.lock` remain the dependency sources used by Docker and local development.
    - Removed the corrupted, superseded `backend/workstatus.md`; this root file remains the canonical work log required by `AGENTS.md`.
    - Removed confirmed broken or obsolete database-analysis, candidate-specific cleanup, legacy embedding, MSSQL-write, code-generation, phase-one migration, and historical-shadow scripts.
    - Removed the confirmed legacy CVAI cutover export/import/backfill helpers and the out-of-band MSSQL dependency/drop scripts.
    - Preserved all runtime, bootstrap, evaluation, regression, and PostgreSQL migration assets, including `department_domains_seed.json`.
    - Documented retained bootstrap/seed and manual evaluation/reprocessing commands in `README.md`; no build, test, migration, seed, or reprocessing command was executed.
1. **2026-08-13 Phase 4 Data/Bootstrap Deep Reference Audit**:
    - Inventoried all tracked backend JSON datasets, PostgreSQL/MSSQL migrations, and operational/bootstrap scripts, then traced static references, dynamic path loading, Docker, CI, documentation, and tests.
    - Confirmed `department_domains_seed.json` remains required by `seed_department_domains.py` and taxonomy seed-validation tests; PostgreSQL migration 005 creates its table but does not populate it.
    - Confirmed `confidence_calibration.json` is runtime-loaded, while `llm_reliability_v1.json` and `regression_cvs.json` are maintained evaluation/regression assets.
    - Classified all PostgreSQL up/down migrations, the migration runner, drift verifier, container health check, documented reset script, and current seed/evaluation scripts as retained assets.
    - Identified broken or obsolete removal candidates without deleting them: `analyze_db_schema.py`, `audit_db_integrity.py`, both legacy embedding backfills, the MSSQL-writing required-skills backfill, `generate_mssql_models.py`, `migrate_phase1_inventory.py`, and `run_historical_shadow_validation.py`.
    - Marked legacy CVAI backfill/export/import helpers plus the MSSQL dependency/drop scripts for cutover-owner confirmation before removal; no application, data, migration, or script file was changed.
1. **2026-08-13 Historical Artifact Audit — `backend/workstatus.md`**:
    - Confirmed the backend-local work log has no repository references, is not the `AGENTS.md`-mandated canonical log, and was last changed before the actively maintained root `workstatus.md`.
    - Found that it begins with a literal `<truncated 54 lines>` corruption marker and includes superseded implementation/verification claims, making it unreliable even as an unqualified archive.
    - Recommended removal rather than continued maintenance or archival; Git history already preserves the useful engineering record. No file was moved or removed during this audit.
1. **2026-08-13 Dependency File Audit — `backend/requirements.txt`**:
    - Audited tracked and untracked repository CI/CD configuration, Dockerfiles, Compose files, scripts, and documentation for `requirements.txt` and `pip install -r` usage.
    - Confirmed the maintained Docker workflow copies `pyproject.toml` plus `uv.lock` and runs `uv sync --frozen`; local/deployment documentation also uses `uv`.
    - Found no repository consumer of `backend/requirements.txt`; its only current reference is its own generated-file header.
    - Kept `backend/requirements.txt`, `backend/pyproject.toml`, and `backend/uv.lock` unchanged because external server/bootstrap configuration is outside repository visibility and still requires confirmation.
1. **2026-08-13 Scratch File Removal — `test_unknown_fallback.py`**:
    - Reviewed and removed the isolated tracked scratch script `backend/test_unknown_fallback.py`; it contained a developer-machine-specific path, top-level print diagnostics, no assertions, and had no repository references.
    - Left the other Phase 1 candidate files unchanged and did not run builds or tests.
1. **2026-08-13 RQ Worker Restart Collision Diagnosis**:
    - Confirmed the rebuilt Compose worker is restart-looping because Redis retained the old `cv-processing-worker-1` registration from hostname `4b08976a7b87`.
    - Confirmed there is only one Compose CV worker container and the stale registration has a short TTL; no queued-job data was removed and no cleanup command was executed.
1. **2026-08-13 Docker Deployment Command Handoff**:
    - Confirmed the Compose migration service is `migrate-postgres` and provided the migration plus backend rebuild/recreate commands; no commands were executed.
1. **2026-08-13 Hiring Risks Integrity Remediation**:
    - Added normalized PostgreSQL persistence and runtime hydration for arbitrary Hiring Risk policies, including explicit enabled, category, title, source, severity, and manual-review settings.
    - Reworked risk generation around typed `RiskEvidenceEvent.failure_code` identities, with distinct disabled/unknown handling and an explicit education-integrity deferral boundary.
    - Added the versioned PostgreSQL `hiring_risk_explanation` prompt contract and constrained Gemma output to `risk_code`, `title`, and `explanation`; deterministic risk fields remain authoritative.
    - Added prompt-content, prompt-version, model, and policy-version cache identities across LLM generation, match-result reuse, persistence parity, and API reads.
    - Added stale-risk suppression for persisted results and protected-data sanitization for the narrowly scoped Gemma payload.
    - Added focused tests for dynamic policy hydration, tamper rejection, protected-data exclusion, failure isolation, cache-key invalidation, and stale persistence behavior.
    - Per repository instructions, did not run tests/builds, apply migrations, restart services, or mutate live PostgreSQL/cache state.
1. **2026-08-13 End-to-End Hiring Risks Integrity Audit (No Fix Applied)**:
    - Traced deterministic failures through `HiringRiskAnalyzer`, PostgreSQL rule hydration, `PromptService`, the centralized Ollama transport, match/result caches, PostgreSQL result persistence, API output, and frontend rendering.
    - Confirmed the live active rule profile is `system-default-v3`, but it contains no Hiring Risks component; `_hydrate_profile` also has no Hiring Risks branch.
    - Confirmed PostgreSQL contains no `hiring_risk_explanation` prompt row, so the live path uses deterministic explanations and makes no Hiring Risks Gemma call.
    - Found that disabled and unknown policies are represented identically, explanation cache identity omits prompt/model/policy versions, and persisted-result reuse can retain stale risks.
    - Confirmed Hiring Risks are already modeled and rendered by the frontend, and the API returns the persisted match-analysis structure without recalculating risks.
    - No application code, database data, cache data, build, service, or test was changed or executed; only read-only source inspection and PostgreSQL queries were performed.
1. **2026-08-12 Matching Failure Diagnosis (No Fix Applied)**:
    - Traced the supplied worker log to an incomplete tri-state hierarchy migration in commit `7e86c81`.
    - Confirmed `HierarchyClassificationResult.is_hierarchy_valid` and `DynamicTaxonomyService` can emit `None`, while `VacancyFitScoreBreakdown.is_hierarchy_valid` still requires `bool`.
    - Confirmed the resulting Pydantic validation error is caught per vacancy in both scoring passes, causing empty match results while the outer RQ job is still reported as successful.
    - Identified a related static regression: `VacancyFitEvaluator.classify_opening_fit` now trusts the stored status and no longer rejects an explicit `is_hierarchy_valid=False`, contrary to the added tri-state test.
    - Identified a separate non-retryable Ollama HTTP failure affecting optimized matching; the log omits the HTTP status/body, but the request sends `think=True` to `gemma3:4b`, making model capability/request incompatibility the leading cause.
    - No application code was changed and no build, run, or tests were executed.
2. **Hierarchy Validation Fix**:
    - Updated the hierarchy-classification schema and producer to use tri-state logic (`True`, `False`, `None`); the downstream score-breakdown schema was missed, as documented above.
    - Added `test_hierarchy_valid_tri_state` to ensure correct handling of all 3 states.
    - Corrected match service logs to clearly separate domain validity, hierarchy validity, and final genuine match decisions.
3. **Seed Data Migration**:
    - Audited and converted all legacy string keywords in `department_domains_seed.json` to the new `KeywordConfig` schema (`term`, `match_type`, `weight`).
    - Configured "IT" as a `CASE_SENSITIVE_ACRONYM` to fix the false-positive pronoun bug.
4. **Taxonomy Fix Validation**:
    - Verified that short-acronyms like HR and QA correctly maintain recall as `CASE_INSENSITIVE_TOKEN`.
    - Added/updated tests in `test_domain_matching.py` (`test_case_insensitive_lowercase_qa`, `test_genuine_active_vacancy_match`) and resolved test mock mismatches to ensure the new matching engine passes unit validation.
5. **Hiring Risks and Concerns Architecture (Chunk 9B)**:
    - Added `HiringRisk` schema and dynamic `HiringRiskConfig` to `app/core/rule_config_manager.py` to drive risk severity and policies.
    - Implemented `HiringRiskAnalyzer` to deterministically translate evaluation gaps (Missing Skills, Minimum Experience, Domain Caps, Unparseable Experience) into structured risks.
    - Integrated Gemma (`OllamaLLMService._execute_structured_generation`) to act merely as a human-readable explanation translator for the deterministic evidence. 
    - Forced all AI generation to respect strict JSON schema guarantees and ignore any hallucinated risks.
    - Verified all edge-cases via a robust test suite (`tests/test_hiring_risk_analyzer.py`), confirming that score and match states remain entirely immutable during this phase.

## Pending Work / Side Effects Found
- Rebuild/recreate the API and worker containers to activate the lock-inclusive Ollama deadlines and non-blocking health handlers, then verify `/health` returns within the configured tags deadline during a long generation.
- Run `backend/tests/test_phase5_ollama_standardization.py` and `backend/tests/test_phase6_api_reliability.py` when test execution is explicitly authorized.
- Capture the matching RQ worker and Ollama container logs for analysis run `cvjob_e983567ad39b44d3924de9aaff727defb9968171b5b89c2de492d6af5d603d5e-1` before changing timeout or health-check behavior; the supplied attachment contains only API-container logs.
- Investigate why Docker lost API-to-Ollama network reachability around 16:01:35 and why Redis ping timed out at 15:59:15; these are the direct dependency failures in the trace.
- Consider a separately scoped readiness/liveness design so `/health` does not queue behind long Ollama generation work, and review frontend status-poll deduplication/backoff to prevent a post-stall request burst.
- Run the focused legacy mandatory-failure compatibility regression test and rebuild/recreate the API container when execution is explicitly authorized.
- Rebuild/recreate the API and worker containers, then reprocess legacy candidates whose stored provenance still contains literal `missing`; new processing will persist `default-1.0.0` and its content identity automatically.
- Run the focused frontend regression tests, TypeScript check, and lint when execution is explicitly authorized.
- Recreate the API and worker containers so `OLLAMA_MODEL=llama3.2:3b` becomes active, then verify startup model discovery.
- Rebuild/recreate the API container so nullable canonical experience is handled by the recommendations endpoint, then reload `/cv_1764311881`.
- Rebuild/recreate the API and worker containers so the optimized-match token budget takes effect, then reprocess the affected CV and confirm `done_reason=stop` in runtime logs.
- Rebuild and recreate the auxiliary and primary worker containers so their new unique RQ identities take effect; old Redis registrations can expire naturally.
- Rebuild/recreate the API and worker containers so the nullable hierarchy response contract takes effect, then reprocess the failed CV job.
- Rebuild the `migrate-postgres` image before retrying migrations; `docker compose run` alone can reuse the pre-fix image.
- Apply `backend/scripts/migrations/postgres/026_ollama_response_integrity.sql`, then rebuild/recreate backend services so prompt version `3.6`, timeout settings, and transport diagnostics become active.
- Run the focused Ollama service/transport and prompt-readiness tests when execution is authorized.
- The backend suite is not currently green: the latest full run reported 106 failures and 571 passes. This cleanup did not attempt broad product-code or substantive-test remediation.
- The three preserved legacy test modules now live under `backend/tests/`, but 7 of their 11 tests expose outdated contracts and require a separate behavioral/test-contract decision.
- Apply `backend/scripts/migrations/postgres/025_hiring_risks_integrity.sql` through the normal deployment process, then restart application/worker processes so the active policy and prompt are loaded.
- Run the focused Hiring Risks tests and the broader regression suite when execution is authorized; tests were added but intentionally not executed during this task.
- The full test suite (`pytest tests/`) reported 72 failures (out of 624 tests) previously regarding schema updates. These are still pending structural fix actions.
- *Side Effect Found* -> Legacy Tests expecting old keyword structures -> *Required Adjustment*: Update mocks in `test_classification_normalization.py`, `test_department_domain_repository.py`, and other taxonomy tests.

## Important Decisions
- Counted Ollama lock acquisition against each operation's existing total timeout instead of adding a second health client or bypassing the centralized transport.
- Preserved `/health` dependency fields and 200/503 readiness semantics; only execution scheduling changed, with independent synchronous probes now running concurrently off the event loop.
- Applied the absolute-deadline contract consistently to tags, generation, embeddings, and explicit unload operations so timeout meaning does not vary by operation.
- Treated the attached trace as diagnostic evidence only: it proves the canonical candidate response contract succeeded and does not justify changing re-analysis persistence or correlation propagation.
- Did not interpret context-free `/api/tags` probes as missing correlation; candidate/run identifiers are correctly unavailable for health checks.
- Kept the Ollama transport, health endpoint, and polling behavior unchanged until worker/Ollama logs establish whether the long shared-lock hold is expected inference time or a transport defect.
- Kept `failure_code` required in the canonical schema and restored only missing legacy values at validation time, preserving the current response contract and producer discipline.
- Used exact current evaluator identities for recognized historical requirement IDs and a neutral fallback for unknown legacy types to avoid inventing a specific hiring-risk classification.
- Used a code-level built-in hiring-risk prompt only as a database-unavailable fallback; active database prompt customization remains authoritative and no duplicate Ollama client or generation path was introduced.
- Derived the default prompt identity from the exact centralized template content so cache invalidation occurs automatically if that maintained fallback changes.
- Replaced silent conditional omission with explicit empty or legacy states on candidate detail; absence of risks or version metadata is now visible and distinguishable from a rendering failure.
- Kept empty Hiring Risks feedback limited to the top vacancy match so multi-match pages do not repeat a success card for every evaluated opening.
- Reused the existing full-profile configuration version workflow so hiring-risk edits remain atomic with scoring rules and activate through the backend's established audit path.
- Kept deterministic evidence separate from the recruiter-facing explanation in the UI so LLM-enhanced copy never obscures the backend facts that produced a risk.
- Exposed processing provenance only in the existing Processing Pipeline tab, keeping operational identifiers out of the primary recruiter overview.
- Classified today's frontend work as targeted parity work rather than a broad endpoint rewrite; backend-only reliability and deployment changes need no UI implementation.
- Preserved `is_hierarchy_valid=null` as eligible for normal deterministic matching while requiring distinct informational UI copy from both confirmed valid and confirmed invalid hierarchy states.
- Retained the repository-root `.env` as Docker's only Ollama model value source; Compose validates and passes it through without its own model fallback.
- Kept unknown experience duration distinct from confirmed zero experience; recommendations may display the canonical assessment but must not perform numeric comparisons on `None`.
- Gave `optimized_match` a dedicated context setting instead of increasing the context and memory footprint of every generation operation.
- Classified `done_reason=length` as non-retryable because the retry payload and deterministic generation settings are unchanged.
- Preserved hierarchy validity as a tri-state value rather than coercing unknown validation to `true` or `false`; only confirmed hierarchy mismatches are hard rejections.
- Avoided deleting or force-unregistering the existing RQ worker because Redis cannot safely distinguish a stale registration from a live worker solely by name; unique per-process names remove the collision safely.
- Execute only trusted repository migration-file contents with `exec_driver_sql`; retain bound parameters for application SQL and migration metadata operations.
- Versioned the corrected optimized prompt as `3.6` instead of editing the active `3.5` record in place so prompt-version cache identities are invalidated deterministically.
- Preserved migration 024 unchanged because the migration runner checks applied-file SHA-256 values; all database correction is isolated in forward migration 026.
- Limited persisted prompt cleanup to global model-neutral prompt records; tenant- or model-specific prompt contracts are not rewritten.
- Retained deterministic fallback behavior but made every generation fallback and embedding throttle decision explicit in logs.
- Classified the endpoint and non-streaming parser as correct based on both source inspection and a live local response; identified prompt compatibility and swallowed diagnostic context as the remaining response defects.
- Treat Ollama's `think` field as capability-specific and omit it for non-thinking models rather than sending `false`; do not mix model-specific slash directives into shared prompts.
- Kept the repository-root `.env` as the sole Docker value source for `OLLAMA_MODEL`; `docker-compose.yml` validates and passes it through, while environment-specific Compose files inherit it.
- Kept the Docker Ollama model check diagnostic-only; did not change `.env`, Compose files, or running containers without an explicit fix/redeploy request.
- Preserved assertion-based tests even when currently failing; cleanup did not hide product regressions by deleting substantive coverage.
- Removed only files with no repository consumer and clear scratch, diagnostic, generated, obsolete migration-helper, or developer-only behavior.
- Kept PostgreSQL as the only writable application database path and removed legacy helpers that imported removed engine aliases or attempted MSSQL mutation.
- Kept `department_domains_seed.json` because fresh migrations create but do not populate `DepartmentDomainMaster`; the explicit seeder and taxonomy tests still consume it.
- Kept every PostgreSQL up/down migration because the migration runner discovers them dynamically by filename.
- Kept risk identity and all decision fields deterministic; Gemma can update only recruiter-facing title and explanation for risk codes already emitted by the analyzer.
- Treat unknown policies as safe ignored events, disabled configured policies as explicitly suppressed events, and education evidence as deferred regardless of policy configuration.
- Suppress stale persisted Hiring Risks instead of recalculating them in repository/API layers; full CV processing remains the single generation path.
- Included prompt content identity in addition to its version tag so an in-place prompt edit cannot reuse an old explanation cache entry after PromptService invalidation.
- Treated the audit as diagnostic-only and did not apply fixes, execute tests/builds, mutate the live database, or clear caches.
- Used the running PostgreSQL container only for read-only verification of active prompt and rule-profile state.
- Kept this task diagnostic-only: no application fixes, test execution, build, service run, cache mutation, or database operation was performed.
- Kept the `department_domain_repository` loading logic intact to respect the existing data-driven workflow, modifying only the seed initialization schema.
- Added `QA Team` to the `conftest.py` repository mock to allow `test_domain_matching.py` to properly test case-insensitive matching for `qa`.
- To guarantee we don't break fallback taxonomy matching logic but maintain proper capitalization intent, only words `len <= 3` and strictly `.isalpha()` are routed to case-sensitive acronym generation.
- Original casing is injected natively into `CandidateResumeDTO` during initialization, replacing forced lowercasing. The regular keyword matching ignores the original casing anyway via `re.IGNORECASE`, minimizing any blast radius across legacy domain matchings.
- The `HiringRiskAnalyzer` relies strictly on deterministic `match_result` failures; Gemma acts purely as an explanation generator, preserving full explainability and pipeline integrity.

## Files Changed
- `backend/app/services/ollama_transport.py`
- `backend/app/main.py`
- `backend/app/api/analysis.py`
- `backend/tests/test_phase5_ollama_standardization.py`
- `backend/tests/test_phase6_api_reliability.py`
- `workstatus.md` (Ollama health backpressure fix recorded)
- `workstatus.md` (API runtime trace audit recorded; no production code changed)
- `backend/app/schemas/match.py`
- `backend/tests/test_legacy_mandatory_failure_compatibility.py`
- `workstatus.md` (legacy mandatory-failure response compatibility fix recorded)
- `backend/app/services/prompt_service.py`
- `backend/app/services/hiring_risk_analyzer.py`
- `backend/scripts/seed_prompts.py`
- `backend/tests/test_prompt_service.py`
- `backend/tests/test_hiring_risk_analyzer.py`
- `frontend/src/utils/processingProvenance.ts`
- `frontend/src/__tests__/backendParity.test.ts`
- `workstatus.md` (default hiring-risk prompt and identity recorded)
- `frontend/src/app/candidates/[id].tsx` (candidate-detail empty and legacy card states)
- `frontend/src/components/ui/HiringRisksCard.tsx` (explicit no-active-risk state)
- `frontend/src/utils/processingProvenance.ts`
- `frontend/src/__tests__/backendParity.test.ts` (processing-provenance regression coverage)
- `workstatus.md` (candidate detail visibility fix recorded)
- `frontend/src/types/api.ts`
- `frontend/src/services/configService.ts`
- `frontend/src/app/config.tsx`
- `frontend/src/app/candidates/[id].tsx`
- `frontend/src/components/ui/HiringRisksCard.tsx`
- `frontend/src/components/ui/VacancyMatchStatusBadge.tsx`
- `frontend/src/utils/hiringRisk.ts`
- `frontend/src/utils/hierarchyValidation.ts`
- `frontend/src/__tests__/backendParity.test.ts`
- `frontend/src/__tests__/hiringRiskConfig.test.ts`
- `workstatus.md` (frontend parity implementation recorded)
- `workstatus.md` (frontend gap audit for today's backend implementations recorded)
- `.env`
- `workstatus.md` (Docker Ollama model alignment to `llama3.2:3b` recorded)
- `backend/app/services/recommendation_service.py`
- `backend/tests/test_ai_recommendations.py`
- `workstatus.md` (nullable canonical experience recommendation fix recorded)
- `backend/app/core/config.py`
- `backend/app/services/llm_service.py`
- `backend/app/services/ollama_transport.py`
- `backend/.env.example`
- `.env`
- `docker-compose.yml`
- `docker-compose.local.yml`
- `README.md`
- `backend/tests/test_qwen_llm_service.py`
- `backend/tests/test_phase5_ollama_standardization.py`
- `workstatus.md` (optimized-match output budget fix recorded)
- `backend/app/schemas/match.py`
- `frontend/src/types/api.ts`
- `backend/tests/test_vacancy_fit_scoring.py`
- `workstatus.md` (vacancy hierarchy tri-state validation fix recorded)
- `backend/app/core/rq_worker_identity.py`
- `backend/start_aux_worker.py`
- `backend/start_worker.py`
- `backend/tests/test_aux_worker.py`
- `backend/tests/test_worker_cleanup.py`
- `backend/tests/test_rq_worker_identity.py`
- `workstatus.md` (RQ worker registration collision fix recorded)
- `backend/scripts/run_migrations.py`
- `backend/tests/test_migration_runner.py`
- `workstatus.md` (PostgreSQL migration JSON bind-parsing fix recorded)
- `backend/app/core/config.py`
- `backend/app/services/embedding_service.py`
- `backend/app/services/llm_service.py`
- `backend/app/services/match_service.py`
- `backend/app/services/ollama_transport.py`
- `backend/app/services/prompt_service.py`
- `backend/scripts/seed_prompts.py`
- `backend/scripts/migrations/postgres/026_ollama_response_integrity.sql`
- `backend/scripts/migrations/postgres/026_ollama_response_integrity_down.sql`
- `backend/tests/test_phase5_ollama_standardization.py`
- `backend/tests/test_prompt_service.py`
- `backend/tests/test_qwen_llm_service.py`
- `.env`
- `backend/.env`
- `backend/.env.example`
- `docker-compose.yml`
- `docker-compose.local.yml`
- `README.md`
- `workstatus.md` (Ollama response integrity remediation recorded)
- `workstatus.md` (end-to-end Ollama response audit recorded)
- `backend/app/services/ollama_transport.py`
- `backend/app/services/llm_service.py`
- `backend/tests/test_qwen_llm_service.py`
- `workstatus.md` (Gemma 3 generation compatibility fix recorded)
- `.env`
- `docker-compose.yml`
- `docker-compose.local.yml`
- `README.md`
- `workstatus.md` (Docker Ollama model consolidation recorded)
- `workstatus.md` (Docker Ollama model configuration check recorded)
- Root-level backend scratch/debug/patch/print/cache/database helper files (removed; see Git status for the complete enumerated set)
- `backend/audit_output.log` (removed generated output)
- `backend/tests/debug_test.py` (removed print-only debug test)
- `backend/test_education.py` -> `backend/tests/test_education_requirement_matching.py`
- `backend/test_relevant_exp.py` -> `backend/tests/test_relevant_experience.py`
- `backend/test_score_ownership.py` -> `backend/tests/test_score_ownership.py`
- `backend/test_lexical_1215.py` (removed)
- `backend/check_plant_exp.py` (removed)
- `backend/test_top10.py` (removed)
- `backend/test_rrf_rank.py` (removed)
- `backend/test_candidate_1760668444.py` (removed)
- `README.md`
- `backend/requirements.txt` (removed)
- `backend/workstatus.md` (removed)
- `backend/scripts/analyze_db_schema.py` (removed)
- `backend/scripts/audit_db_integrity.py` (removed)
- `backend/scripts/backfill_cvai_cache.py` (removed)
- `backend/scripts/backfill_embeddings.py` (removed)
- `backend/scripts/backfill_required_skills_from_job_profile_desc.py` (removed)
- `backend/scripts/backfill_vacancy_embeddings.py` (removed)
- `backend/scripts/check_mssql_dependencies.sql` (removed)
- `backend/scripts/data_migration/export_mssql_cvai.py` (removed)
- `backend/scripts/data_migration/import_pg_cvai.py` (removed)
- `backend/scripts/generate_mssql_models.py` (removed)
- `backend/scripts/migrate_phase1_inventory.py` (removed)
- `backend/scripts/migrations/mssql/002_drop_cvai_schema.sql` (removed)
- `backend/scripts/run_historical_shadow_validation.py` (removed)
- `backend/test_unknown_fallback.py` (removed)
- `backend/app/services/configuration_service.py`
- `backend/app/services/cv_service.py`
- `backend/app/services/match_service.py`
- `backend/app/services/prompt_service.py`
- `backend/app/repositories/result.py`
- `backend/scripts/seed_prompts.py`
- `backend/scripts/migrations/postgres/025_hiring_risks_integrity.sql`
- `backend/scripts/migrations/postgres/025_hiring_risks_integrity_down.sql`
- `backend/tests/conftest.py`
- `backend/tests/test_cache_hit_persistence.py`
- `backend/tests/test_configuration_schema.py`
- `backend/tests/test_prompt_service.py`
- `workstatus.md`
- `backend/app/repositories/department_domain.py`
- `backend/app/services/job_taxonomy.py`
- `backend/app/services/candidate_domain_service.py`
- `backend/tests/test_domain_matching.py`
- `backend/tests/conftest.py`
- `backend/app/schemas/match.py`
- `backend/app/core/rule_config_manager.py`
- `backend/app/services/system_rule_config_factory.py`
- `backend/app/services/hiring_risk_analyzer.py`
- `backend/app/services/scoring_engine.py`
- `backend/tests/test_hiring_risk_analyzer.py`
