from __future__ import annotations
import asyncio
import hashlib
from pathlib import Path
from typing import Any, cast

from app.core.analysis_context import get_analysis_run_id
from app.core.cache import CacheIndex, CacheKey, match_result_cache_manager
from app.core.config import settings
from app.core.cv_identity import normalize_source_candidate_id
from app.core.logging import logger
from app.core.profiler import PipelineProfiler
from app.core.rule_config_manager import RuleConfigManager
from app.prompts.optimized_match import build_optimized_match_prompt
from app.repositories.job import JobRepository, VacancyLoadStatus, VacancySourceUnavailableError
from app.repositories.llm_cache import LLMCacheRepository
from app.repositories.department_domain import department_domain_repository
from app.repositories.result import ResultRepository
from app.schemas.analysis import EnrichedCandidateAnalysis, EnrichedJobMatchResult
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.classification_types import AISuggestion, ClassificationEvidence, MatchStatus, NormalizedClassification
from app.schemas.job_context import JobEvaluationContext
from app.schemas.normalized_resume import NormalizedResume
from app.services.candidate_domain_service import CandidateDomainService
from app.services.confidence_calibration import ConfidenceCalibrationService
from app.services.document_parser import ResumeJsonExtractor
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
from app.services.hiring_risk_analyzer import HiringRiskAnalyzer
from app.services.llm_grounding_service import GroundingReport, LLMGroundingService
from app.services.llm_service import OllamaLLMService
from app.services.matching_quality_gate import MatchingQualityGate, MatchingReadiness
from app.services.ollama_transport import OllamaError
from app.services.prompt_service import PromptService
from app.services.resume_normalizer import ResumeNormalizer
from app.services.scoring_engine import ScoringEngine
from app.services.vacancy_prefilter import VacancyPreFilter


class MatchService:
    @staticmethod
    async def analyze_single_cv(
        cv_text: str,
        job_openings: list[dict[str, Any]] | None = None,
        candidate_experience: float | None = None,
        candidate_ctc: float | None = None,
        document_hash: str = "",
        candidate_id: str = "",
        cv_key: str = "",
        source_candidate_id: int | None = None,
        upload_ms: float = 0.0,
        docling_extraction_ms: float = 0.0,
        cv_embedding: list[float] | None = None,
        resume_json: dict[str, Any] | None = None,
        normalized_resume: NormalizedResume | None = None,
        deterministic_experience: float | None = None,
        force_reanalysis: bool = False,
        _shadow_run: bool = False,
    ) -> EnrichedCandidateAnalysis:
        profiler = PipelineProfiler()
        profiler.metrics.upload_ms = upload_ms
        profiler.metrics.docling_extraction_ms = docling_extraction_ms

        # 1. Validate CV text is meaningful (not just image markers from failed OCR)
        if not cv_text or not cv_text.strip():
            raise ValueError("CV text content cannot be empty.")

        cv_stripped = cv_text.strip()
        if "<!-- image -->" in cv_stripped and len(cv_stripped) < 50:
            raise ValueError("CV document is a scanned image with no extractable text. OCR could not extract any meaningful content.")

        document_hash = (document_hash or "").strip() or hashlib.sha256(cv_text.encode("utf-8")).hexdigest()
        cv_key = str(cv_key or candidate_id).strip()
        analysis_run_id = get_analysis_run_id()
        logger.info(f"analysis_run_id={analysis_run_id} candidate={cv_key or 'not_available'} operation=match_analysis status=START")
        source_candidate_id = normalize_source_candidate_id(source_candidate_id)
        extraction_version = f"{settings.EXTRACTION_PARSER_VERSION}:{settings.EXTRACTION_SCHEMA_VERSION}"
        quality_gate = MatchingQualityGate()

        # 2. JSON Loading stage timing (parsing CV text input)
        with profiler.time_stage("resume_json"):
            if resume_json is None:
                try:
                    resume_json = ResumeJsonExtractor.extract(cv_text)
                except Exception as e:
                    logger.warning(f"ResumeJsonExtractor failed in match_service: {e}")
                    resume_json = {}
            if normalized_resume is None:
                normalized_payload = resume_json.get("normalized") if resume_json else None
                normalized_resume = NormalizedResume.model_validate(normalized_payload) if normalized_payload else ResumeNormalizer.normalize(resume_json or {}, cv_text)

        quality_gate.record(
            "extraction_quality",
            "PASSED",
            skill_count=len(normalized_resume.skills),
            employment_count=len(normalized_resume.employment),
            education_count=len(normalized_resume.education),
        )

        readiness = MatchingQualityGate.check_runtime_readiness()
        if not readiness.ready:
            return MatchService._unavailable_analysis(normalized_resume, readiness, quality_gate)

        if deterministic_experience is None:
            deterministic_experience = normalized_resume.experience.authoritative_years

        from fastapi.concurrency import run_in_threadpool

        # 3. Vacancy retrieval
        vacancy_freshness = "FRESH"
        with profiler.time_stage("vacancy_retrieval"):
            if job_openings is not None:
                openings = job_openings
            else:
                try:
                    vacancy_result = await run_in_threadpool(JobRepository.load_all_jobs)
                except VacancySourceUnavailableError:
                    readiness = MatchingReadiness(
                        False,
                        "VACANCY_SOURCE_UNAVAILABLE",
                        "The active vacancy source is unavailable and no safe snapshot can be evaluated.",
                    )
                    return MatchService._unavailable_analysis(normalized_resume, readiness, quality_gate)
                openings = vacancy_result.jobs
                if vacancy_result.status == VacancyLoadStatus.STALE:
                    vacancy_freshness = "STALE"
                    if not openings:
                        readiness = MatchingReadiness(
                            False,
                            "VACANCY_SOURCE_UNAVAILABLE",
                            "The active vacancy source is unavailable and the cached vacancy snapshot is empty.",
                        )
                        return MatchService._unavailable_analysis(normalized_resume, readiness, quality_gate)

        if not openings:
            logger.warning("MatchService.analyze_single_cv: Authoritative vacancy source contains no active openings.")
            profiler.finish()
            profiler.log_summary()
            quality_gate.record("vacancy_retrieval", "PASSED_EMPTY", source_count=0, retrieved_count=0)
            quality_gate.record("final_classification", "PASSED", match_status="NO_ACTIVE_VACANCIES", final_score=None)
            return MatchService._empty_analysis(cv_text=cv_text, normalized_resume=normalized_resume, quality_gate=quality_gate, is_global_empty=True)

        profiler.metrics.vacancies_before_filtering = len(openings)

        vacancy_ids = sorted(str(job.get("vacancy_id") or job.get("id") or "") for job in openings if job.get("vacancy_id") is not None or job.get("id") is not None)
        vacancy_version = JobRepository.compute_matching_vacancy_version(openings)
        rule_config = RuleConfigManager.get_config()
        rule_version = rule_config.version
        hiring_risk_policy_version = HiringRiskAnalyzer.get_policy_version(rule_config)
        taxonomy_version = department_domain_repository.get_version()
        hiring_risk_prompt_version = PromptService.get_active_prompt_version(HiringRiskAnalyzer.PROMPT_NAME) or "missing"
        hiring_risk_prompt_identity = PromptService.get_active_prompt_identity(HiringRiskAnalyzer.PROMPT_NAME) or "missing"
        match_prompt_version = f"optimized:{settings.OPTIMIZED_PROMPT_VERSION}|hiring-risk:{hiring_risk_prompt_identity}"

        # 4. Match Result Cache Check (instant repeat searches)
        t_cache_start = asyncio.get_event_loop().time()
        match_cache_key = CacheKey.for_match_result(
            document_hash=document_hash,
            candidate_id=cv_key,
            vacancy_version=vacancy_version,
            vacancy_ids=vacancy_ids,
            prompt_version=match_prompt_version,
            model_version=settings.OLLAMA_MODEL,
            extraction_version=extraction_version,
            matching_version=settings.MATCHING_VERSION,
            rule_version=f"{rule_version}|hiring-risk:{hiring_risk_policy_version}",
            taxonomy_version=taxonomy_version,
        ).to_key()

        cached_result = None if force_reanalysis else match_result_cache_manager.get(match_cache_key)
        if cached_result is not None:
            logger.info(f"[MATCH_CACHE_HIT] Returning cached match result for doc={document_hash[:12]}...")
            profiler.metrics.cache_hit = True
            profiler.metrics.cache_lookup_ms = round((asyncio.get_event_loop().time() - t_cache_start) * 1000.0, 2)
            profiler.finish()
            profiler.log_summary()
            cached_analysis = EnrichedCandidateAnalysis.model_validate(cached_result).model_copy(
                update={"freshness_status": vacancy_freshness}
            )
            MatchService._enqueue_shadow_if_requested(
                cached_analysis,
                source_candidate_id=source_candidate_id,
                cv_text=cv_text,
                shadow_run=_shadow_run,
            )
            return cached_analysis
        profiler.metrics.cache_lookup_ms = round((asyncio.get_event_loop().time() - t_cache_start) * 1000.0, 2)

        with profiler.time_stage("candidate_context"):
            candidate_context = CandidateAnalysisContext.create(
                cv_text=cv_text,
                candidate_experience=candidate_experience,
                candidate_ctc=candidate_ctc,
                resume_json=resume_json,
                normalized_resume=normalized_resume,
                deterministic_experience=deterministic_experience,
                domain_repository=ScoringEngine.domain_repository,
            )
        quality_gate.record(
            "candidate_evidence_profile",
            "PASSED",
            current_role=candidate_context.current_role,
            skill_count=len(candidate_context.professional_skills),
            experience_years=candidate_context.candidate_experience,
        )
        quality_gate.record(
            "taxonomy_classification",
            "PASSED" if candidate_context.cand_tax_domain not in ("", "Unknown") else "INSUFFICIENT_EVIDENCE",
            domain=candidate_context.cand_tax_domain or "Unknown",
            families=candidate_context.cand_families,
            confidence=round(candidate_context.taxonomy_confidence, 4),
            match_status=candidate_context.taxonomy_match_status,
            source=candidate_context.taxonomy_match_source,
        )
        from app.services.vacancy_prefilter import InsufficientEvidenceError, AnalysisUnavailableError
        # 5. Python Pre-filter stage (Stage 0 Taxonomy + Stage 1 Vector + Stage 2 RRF)
        with profiler.time_stage("prefilter"):
            try:
                filtered_job_contexts = cast(
                    list[JobEvaluationContext],
                    VacancyPreFilter.filter_vacancies(
                        cv_text=cv_text,
                        openings=openings,
                        candidate_experience=candidate_context.candidate_experience,
                        top_k=settings.PREFILTER_TOP_K,
                        cv_embedding=cv_embedding,
                        resume_json=resume_json,
                        analysis_context=candidate_context,
                        return_contexts=True,
                    ),
                )
            except InsufficientEvidenceError as exc:
                logger.warning(f"Insufficient evidence for candidate match: {exc}")
                readiness = MatchingReadiness(False, "INSUFFICIENT_EVIDENCE", str(exc))
                return MatchService._unavailable_analysis(normalized_resume, readiness, quality_gate, status=MatchStatus.INSUFFICIENT_EVIDENCE)
            except AnalysisUnavailableError as exc:
                logger.error(f"Analysis unavailable: {exc}")
                readiness = MatchingReadiness(False, "ANALYSIS_UNAVAILABLE", str(exc))
                return MatchService._unavailable_analysis(normalized_resume, readiness, quality_gate, status=MatchStatus.ANALYSIS_UNAVAILABLE)
        filtered_vacancies = [job.raw_job for job in filtered_job_contexts]
        profiler.metrics.vacancies_after_filtering = len(filtered_job_contexts)
        quality_gate.record(
            "vacancy_retrieval",
            "PASSED",
            source_count=len(openings),
            retrieved_count=len(filtered_job_contexts),
            top_vacancy_ids=[job.job_id for job in filtered_job_contexts[:10]],
        )

        from app.schemas.scoring_config import ScoringConfig
        scoring_config = ScoringConfig.load()

        # Pre-compute hierarchy classification for vacancy scoring & hierarchy fit evaluation
        hierarchy_res = DynamicTaxonomyService.classify_organization_hierarchy(
            role_or_summary=candidate_context.current_role or "",
            skills=candidate_context.professional_skills,
            domain=candidate_context.cand_domain or candidate_context.cand_tax_domain,
            experience_years=candidate_context.candidate_experience,
            cv_text=cv_text,
        )
        candidate_context.cand_hierarchy = hierarchy_res

        # CONFIDENCE GATE CHECK (Phase 3)
        llm_skipped = False
        pre_llm_matches = []
        if filtered_job_contexts:
            for job_context in filtered_job_contexts:
                try:
                    pre_llm_match = ScoringEngine.evaluate_job_match(
                        cv_text=cv_text,
                        job=job_context,
                        llm_match=None,
                        scoring_config=scoring_config,
                        context=candidate_context,
                        cand_hierarchy=candidate_context.cand_hierarchy,
                    )
                    pre_llm_matches.append(pre_llm_match)
                except OllamaError:
                    raise
                except Exception as e:
                    logger.error(f"Error in rule-based matching for job {job_context.job_id}: {e}", exc_info=True)

            pre_llm_matches.sort(key=lambda m: m.score, reverse=True)
            if pre_llm_matches:
                top_score = pre_llm_matches[0].score
                top_coverage = pre_llm_matches[0].coverage
                second_score = pre_llm_matches[1].score if len(pre_llm_matches) > 1 else 0.0
                if top_coverage >= settings.LLM_SKIP_COVERAGE_THRESHOLD and (top_score - second_score) >= settings.LLM_SKIP_MARGIN_THRESHOLD:
                    logger.info(f"Unambiguous rule-based match found (Score: {top_score}, Margin: {round(top_score - second_score, 1)}). Skipping LLM.")
                    llm_skipped = True

        optimized_response = None
        optimized_profile = None
        llm_matches_map = {}
        grounding_report = GroundingReport()
        raw_llm_lineage: dict[str, dict[str, int]] = {}
        grounded_llm_lineage: dict[str, dict[str, int]] = {}

        if not llm_skipped:
            # 4. Reduce LLM input to Top-N by deterministic score (full scoring already computed above).
            # pre_llm_matches is sorted desc by score; use that ordering to select Top-N for LLM enrichment.
            llm_top_n = settings.LLM_TOP_N
            if pre_llm_matches:
                # Build job_id→JobEvaluationContext lookup for O(1) access
                jc_by_id = {jc.job_id: jc for jc in filtered_job_contexts}
                llm_vacancies = []
                for pm in pre_llm_matches[:llm_top_n]:
                    jc = jc_by_id.get(pm.job_id)
                    if jc is not None:
                        llm_vacancies.append(jc)
            else:
                # Fallback: no deterministic scores available, use prefilter RRF score
                llm_vacancies = sorted(
                    filtered_job_contexts,
                    key=lambda jc: jc.raw_job.get("_prefilter_score", 0.0) if isinstance(jc.raw_job, dict) else 0.0,
                    reverse=True,
                )[:llm_top_n]
            llm_vacancy_dicts = [jc.raw_job for jc in llm_vacancies]
            llm_vacancy_ids = {jc.job_id for jc in llm_vacancies}
            pre_llm_score_by_id = {match.job_id: match.score for match in pre_llm_matches}
            for job_context in filtered_job_contexts:
                if job_context.job_id not in llm_vacancy_ids:
                    logger.info(
                        f"[PREFILTER_EXCLUSION] vacancy_id={job_context.job_id} stage=llm_selection "
                        f"reason=DETERMINISTIC_LLM_TOP_N deterministic_score={pre_llm_score_by_id.get(job_context.job_id)} "
                        f"llm_top_n={llm_top_n}"
                    )

            # 5. Prompt Construction & Token Count
            with profiler.time_stage("prompt_construction"):
                prompt, token_est, char_count = build_optimized_match_prompt(cv_text, llm_vacancy_dicts)
                vacancy_count = len(llm_vacancy_dicts)
                profiler.metrics.token_count = token_est
                profiler.metrics.context_char_count = char_count
                profiler.metrics.prompt_vacancy_count = vacancy_count
                profiler.metrics.prompt_input_chars = char_count
                profiler.metrics.prompt_input_tokens = token_est

            full_cv_chars = len(cv_text)
            logger.info(
                f"[LLM_INPUT] doc={document_hash[:12]}... "
                f"full_cv_chars={full_cv_chars} cv_token_budget={settings.LLM_CONTEXT_CV_TOKEN_BUDGET} "
                f"vacancies_prefiltered={len(filtered_job_contexts)} "
                f"vacancies_sent_to_llm={vacancy_count} prompt_chars={char_count} estimated_tokens={token_est}"
            )

            # Compute version-aware cache key (use llm vacancies for more precise keying)
            filtered_vacancy_ids = [str(j.get("vacancy_id") or j.get("id")) for j in llm_vacancy_dicts]
            cache_key = LLMCacheRepository.compute_composite_hash(
                document_hash=document_hash,
                candidate_id=f"{cv_key}:{analysis_run_id}" if force_reanalysis else cv_key,
                vacancy_ids=filtered_vacancy_ids,
                vacancy_version=vacancy_version,
                prompt_version=settings.OPTIMIZED_PROMPT_VERSION,
                model_version=settings.OLLAMA_MODEL,
                extraction_version=extraction_version,
                matching_version=settings.MATCHING_VERSION,
                rule_version=rule_version,
                taxonomy_version=taxonomy_version,
            )

            # 5. Single Optimized LLM Call + Pydantic Validation (with cache check & retries)
            optimized_response = await asyncio.to_thread(
                OllamaLLMService.run_optimized_match,
                prompt,
                settings.OPTIMIZED_PROMPT_VERSION,
                cache_key,
                profiler,
            )

            if optimized_response:
                raw_llm_lineage = {
                    str(match.vacancy_id): {
                        "matched_skills": len(match.matched_skills),
                        "inferred_skills": len(match.inferred_skills),
                        "requirements": len(match.classified_requirements),
                        "evidence": len(match.evidence_snippets),
                        "requirement_assessments": len(match.requirement_assessments),
                    }
                    for match in optimized_response.matched_vacancies
                }
                optimized_response, grounding_report = LLMGroundingService.validate_optimized_response(
                    optimized_response,
                    cv_text=cv_text,
                    vacancies=llm_vacancy_dicts,
                )
                grounded_llm_lineage = {
                    str(match.vacancy_id): {
                        "matched_skills": len(match.matched_skills),
                        "inferred_skills": len(match.inferred_skills),
                        "requirements": len(match.classified_requirements),
                        "evidence": len(match.evidence_snippets),
                        "requirement_assessments": len(match.requirement_assessments),
                    }
                    for match in optimized_response.matched_vacancies
                }
                logger.debug(
                    f"[LLM_LINEAGE] raw_vacancies={len(raw_llm_lineage)} grounded_vacancies={len(grounded_llm_lineage)} "
                    f"invalid_vacancy_ids={len(grounding_report.invalid_vacancy_ids)} "
                    f"missing_vacancy_ids={len(grounding_report.missing_vacancy_ids)} "
                    f"unsupported_claims={len(grounding_report.unsupported_claims)}"
                )
                OllamaLLMService.record_quality_trace(
                    operation="optimized_match_grounding",
                    prompt=prompt,
                    prompt_version=settings.OPTIMIZED_PROMPT_VERSION,
                    source_hash=cache_key,
                    quality_metadata={
                        "grounding_ratio": round(grounding_report.ratio, 4),
                        "assertions": grounding_report.assertions,
                        "grounded_assertions": grounding_report.grounded_assertions,
                        "invalid_vacancy_ids": len(grounding_report.invalid_vacancy_ids),
                        "missing_vacancy_ids": len(grounding_report.missing_vacancy_ids),
                        "unsupported_claims": len(grounding_report.unsupported_claims),
                    },
                )
            else:
                logger.warning(
                    f"[OLLAMA] operation=optimized_match model='{settings.OLLAMA_MODEL}' "
                    "status=DETERMINISTIC_FALLBACK reason=NO_VALID_LLM_RESPONSE"
                )

            optimized_profile = optimized_response.candidate_profile if optimized_response else None
            candidate_context.apply_optimized_profile(
                optimized_profile,
                domain_repository=ScoringEngine.domain_repository,
            )
            if optimized_response:
                for vm in optimized_response.matched_vacancies:
                    llm_matches_map[str(vm.vacancy_id)] = vm

        # 6. Deterministic Scoring & Ranking in Python
        evaluated_matches = []
        with profiler.time_stage("scoring"):
            if optimized_profile:
                logger.info(f"LLM Extracted Experience: {optimized_profile.relevant_experience_years}, LLM Domain: {optimized_profile.professional_domain}")

            for job_context in filtered_job_contexts:
                try:
                    job = job_context.raw_job
                    vac_id_str = str(job.get("vacancy_id") or job.get("id"))
                    llm_match = llm_matches_map.get(vac_id_str)

                    job_match = ScoringEngine.evaluate_job_match(
                        cv_text=cv_text,
                        job=job_context,
                        llm_match=llm_match,
                        scoring_config=scoring_config,
                        context=candidate_context,
                        cand_hierarchy=candidate_context.cand_hierarchy,
                    )

                    # Wrap into EnrichedJobMatchResult
                    llm_reason = llm_match.semantic_reason if llm_match else ""
                    inferred_skills = llm_match.inferred_skills if llm_match else (optimized_profile.inferred_skills if optimized_profile else [])
                    deterministic_skills = {skill.strip().lower() for skill in job_match.matched_skills if skill.strip()}
                    llm_skills = {skill.strip().lower() for skill in (llm_match.matched_skills if llm_match else []) if skill.strip()}
                    agreement = 1.0 if llm_skipped else (len(deterministic_skills & llm_skills) / len(llm_skills) if llm_skills else 0.5)
                    calibration = ConfidenceCalibrationService.calculate(
                        evidence_coverage=job_match.coverage,
                        grounding_ratio=grounding_report.ratio,
                        rule_llm_agreement=agreement,
                        validation_passed=llm_skipped or (optimized_response is not None and llm_match is not None),
                    )
                    retrieval_provenance = dict(job.get("_rrf_details") or {})
                    has_lexical = retrieval_provenance.get("lexical_rank") is not None
                    has_vector = retrieval_provenance.get("vector_rank") is not None
                    retrieval_source = "both" if has_lexical and has_vector else "vector" if has_vector else "keyword"
                    quality_flags = []
                    if calibration.review_recommended:
                        quality_flags.append("LOW_CALIBRATED_CONFIDENCE")
                    if grounding_report.unsupported_claims:
                        quality_flags.append("UNSUPPORTED_LLM_CLAIMS_REMOVED")
                    if optimized_response is not None and llm_match is None:
                        quality_flags.append("LLM_VACANCY_EVALUATION_MISSING")

                    enriched_match = EnrichedJobMatchResult(
                        job_id=job_match.job_id,
                        job_title=job_match.job_title,
                        department=job_match.department,
                        vacancy_id=job_match.vacancy_id,
                        job_profile_id=job_match.job_profile_id,
                        company_id=job_match.company_id,
                        department_id=job_match.department_id,
                        department_name=job_match.department_name,
                        location_id=job_match.location_id,
                        score=job_match.score,
                        overall_score=job_match.overall_score,
                        vacancy_fit_score=job_match.vacancy_fit_score,
                        score_breakdown=job_match.score_breakdown,
                        vacancy_match_status=job_match.vacancy_match_status,
                        role_score=job_match.role_score,
                        skills_score=job_match.skills_score,
                        experience_score=job_match.experience_score,
                        education_score=job_match.education_score,
                        domain_score=job_match.domain_score,
                        technology_score=job_match.technology_score,
                        certification_score=job_match.certification_score,
                        responsibilities_score=job_match.responsibilities_score,
                        coverage=job_match.coverage,
                        ranking_reason=job_match.ranking_reason,
                        classification=job_match.classification,
                        recommendation=job_match.recommendation,
                        matched_skills=job_match.matched_skills,
                        missing_skills=job_match.missing_skills,
                        matched_keywords=job_match.matched_keywords,
                        missing_keywords=job_match.missing_keywords,
                        mandatory_requirements=job_match.mandatory_requirements,
                        preferred_requirements=job_match.preferred_requirements,
                        optional_requirements=job_match.optional_requirements,
                        matched_criteria=job_match.matched_criteria,
                        missing_criteria=job_match.missing_criteria,
                        evidence=job_match.evidence,
                        mandatory_failures=job_match.mandatory_failures,
                        confidence=job_match.confidence,
                        hr_review_required=job_match.hr_review_required,
                        domain_mismatch_capped=job_match.domain_mismatch_capped,
                        domain_mismatch_reason=job_match.domain_mismatch_reason,
                        retrieval_source=retrieval_source,
                        candidate_job_family=job_match.candidate_job_family,
                        vacancy_job_family=job_match.vacancy_job_family,
                        reason=job_match.reason or llm_reason,
                        career_transition_detected=job_match.career_transition_detected,
                        career_transition_note=job_match.career_transition_note,
                        llm_reason=llm_reason,
                        top_strength=llm_match.top_strength if llm_match else "",
                        main_concern=llm_match.main_concern if llm_match else "",
                        ai_match_explanation=llm_match.ai_match_explanation if llm_match else llm_reason,
                        inferred_skills=inferred_skills,
                        calibrated_confidence=calibration.score,
                        calibration_version=calibration.calibration_version,
                        quality_flags=quality_flags,
                        retrieval_provenance=retrieval_provenance,
                        llm_classified_requirements=llm_match.classified_requirements if llm_match else [],
                        llm_evidence_snippets=llm_match.evidence_snippets if llm_match else {},
                        llm_requirement_assessments=llm_match.requirement_assessments if llm_match else [],
                    )
                    evaluated_matches.append(enriched_match)
                    raw_counts = raw_llm_lineage.get(vac_id_str, {})
                    grounded_counts = grounded_llm_lineage.get(vac_id_str, {})
                    logger.debug(
                        f"[LLM_POST_PROCESS] vacancy_id={vac_id_str} raw_counts={raw_counts} grounded_counts={grounded_counts} "
                        f"deterministic_evidence={len(job_match.evidence)} mandatory_failures={len(job_match.mandatory_failures)} "
                        f"final_score={job_match.vacancy_fit_score}"
                    )
                except OllamaError:
                    raise
                except Exception as e:
                    logger.error(f"Error in LLM-enriched matching for job {job_context.job_id}: {e}", exc_info=True)

            evaluated_matches.sort(key=lambda m: m.vacancy_fit_score or m.score, reverse=True)

            if evaluated_matches:
                logger.debug("MATCHING PIPELINE DEBUG OUTPUT")
                for i, m in enumerate(evaluated_matches):
                    if i == 0:
                        m.ranking_reason = f"Ranked #1 with highest verified fit score of {m.vacancy_fit_score or m.score}%."
                    else:
                        m.ranking_reason = (
                            f"Ranked #{i + 1} due to lower fit score ({m.vacancy_fit_score or m.score}% vs top "
                            f"{evaluated_matches[0].vacancy_fit_score or evaluated_matches[0].score}%)."
                        )
                    
                    is_h_valid = getattr(m.score_breakdown, "is_hierarchy_valid", None) if m.score_breakdown else None
                    logger.debug(f"Vacancy {m.vacancy_id} Validity -> domain_validity={not m.domain_mismatch_capped}, hierarchy_validity={is_h_valid}, match_status={m.vacancy_match_status}")

                    evidence_snippet = "; ".join(f"{ev.cv_evidence}" for ev in m.evidence.values())
                    if len(evidence_snippet) > 150:
                        evidence_snippet = evidence_snippet[:147] + "..."
                    if not evidence_snippet:
                        evidence_snippet = "None"

                    fails_snippet = "; ".join(f"{f.description}" for f in m.mandatory_failures) if m.mandatory_failures else "None"

                    logger.debug(
                        f"[VACANCY] ID: {m.vacancy_id} | Title: {m.job_title} | "
                        f"Overall Score: {m.score}% (Coverage: {int(m.coverage * 100)}%) | "
                        f"SubScores: Role={m.role_score}, Skills={m.skills_score}, Exp={m.experience_score}, Edu={m.education_score}, Domain={m.domain_score}, Tech={m.technology_score} | "
                        f"Mandatory Fails: {fails_snippet} | Evidence: {evidence_snippet} | Ranking Reason: {m.ranking_reason}"
                    )

        profiler.finish()
        profiler.log_summary()

        cand_profile = candidate_context.cand_domain_profile
        recommended_dept = cand_profile.get("recommended_department", "")
        professional_domain = cand_profile.get("professional_domain", "")
        strengths = cand_profile.get("strengths", [])
        suitable_roles = cand_profile.get("suitable_job_roles", [])

        from app.services.match_evaluators import VacancyFitEvaluator, VacancyMatchStatus

        strong_threshold = scoring_config.match_high_threshold
        eligible_matches = [
            match
            for match in evaluated_matches
            if VacancyFitEvaluator.is_eligible_match(match, high_threshold=strong_threshold)
        ]
        has_genuine_match = bool(eligible_matches)

        has_potential_match = False
        if has_genuine_match:
            top_m = eligible_matches[0]
            skills_str = ", ".join(top_m.matched_skills[:4]) if top_m.matched_skills else "core qualification requirements"
            active_vacancy_summary = (
                f"Genuine Match Found: Candidate is a strong match for '{top_m.job_title}' "
                f"in the {top_m.department_name or top_m.department} department "
                f"with an overall match score of {top_m.score}%. Key matching skills include {skills_str}."
            )
            best_match = top_m
        elif evaluated_matches:
            potential_matches = [
                m for m in evaluated_matches
                if VacancyFitEvaluator.classify_opening_fit(m, high_threshold=strong_threshold) == VacancyMatchStatus.POTENTIAL_MATCH.value
            ]
            if potential_matches:
                top_p = potential_matches[0]
                has_potential_match = True
                active_vacancy_summary = (
                    f"POTENTIAL_MATCH: Candidate shows potential alignment with '{top_p.job_title}' "
                    f"(Match Score: {top_p.score}%). Manual HR review recommended."
                )
                best_match = top_p
            else:
                active_vacancy_summary = (
                    "NO_STRONG_MATCH: No suitable active vacancy found matching candidate domain/taxonomy profile "
                    f"(Primary Domain: {professional_domain}). Manual HR review recommended."
                )
                best_match = evaluated_matches[0]
        elif not job_openings:
            active_vacancy_summary = "NO_ACTIVE_VACANCIES: No active vacancies available in system for evaluation."
            best_match = None
        else:
            active_vacancy_summary = (
                "NO_STRONG_MATCH: No suitable active vacancy found matching candidate domain/taxonomy profile "
                f"(Primary Domain: {professional_domain}). Manual HR review recommended."
            )
            best_match = None

        roles_str = ", ".join(suitable_roles) if suitable_roles else ""
        strengths_str = "; ".join(strengths) if strengths else ""

        if optimized_response and optimized_response.ai_career_summary:
            ai_career_summary = optimized_response.ai_career_summary
        else:
            ai_career_summary = (
                f"Candidate Profile Analysis:\n"
                f"• Recommended Department: {recommended_dept}\n"
                f"• Professional Domain: {professional_domain}\n"
                f"• Key Strengths: {strengths_str}\n"
                f"• Suitable Job Roles: {roles_str}"
            )

        logger.info(f"Candidate Domain Analysis: dept='{recommended_dept}', domain='{professional_domain}'")
        logger.info(f"Final Genuine-Match Decision: has_genuine_match={has_genuine_match}")

        suitable_matches = eligible_matches
        unsuitable_matches = [m for m in evaluated_matches if m not in eligible_matches]
        quality_gate.record(
            "mandatory_requirement_gate",
            "PASSED",
            rejected_count=sum(bool(match.mandatory_failures) for match in evaluated_matches),
        )
        quality_gate.record("deterministic_fit_score", "PASSED", evaluated_count=len(evaluated_matches))
        quality_gate.record(
            "llm_grounded_enrichment",
            "SKIPPED_CONFIDENT" if llm_skipped else "PASSED" if optimized_response else "UNAVAILABLE_DETERMINISTIC_FALLBACK",
            grounding_ratio=round(grounding_report.ratio, 4),
            unsupported_claims_removed=len(grounding_report.unsupported_claims),
        )
        quality_gate.record(
            "confidence_consistency_gate",
            "PASSED",
            strong_matches=len(eligible_matches),
            contradictory_results=sum(
                match.vacancy_match_status == "MATCHED" and bool(match.mandatory_failures)
                for match in evaluated_matches
            ),
        )

        # Build NormalizedClassification for the candidate from their resolved context
        cand_classification: NormalizedClassification | None = None
        ai_career_suggestions: list[AISuggestion] = []
        try:
            cand_classification = DynamicTaxonomyService.resolve_candidate_role_and_domain(
                role_or_summary=candidate_context.current_role or professional_domain,
                skills=list(candidate_context.cand_families),
            )
            # Populate industry labels if not already set
            if cand_classification and not cand_classification.industry_department:
                cand_classification = cand_classification.model_copy(update={
                    "industry_department": recommended_dept,
                    "industry_domain": professional_domain,
                })
        except Exception as _cls_err:
            logger.warning(f"[MATCH_SERVICE] Could not build NormalizedClassification: {_cls_err}")

        role_suggestion_source = "candidate_domain_profile"
        if not has_genuine_match and not suitable_roles and candidate_context.current_role:
            suitable_roles = [candidate_context.current_role]
            role_suggestion_source = "verified_professional_experience"

        if not has_genuine_match and suitable_roles:
            ai_career_suggestions = [
                AISuggestion(
                    suggested_role=role,
                    suggested_domain=professional_domain,
                    confidence=0.5,
                    evidence=[
                        ClassificationEvidence(
                            source=role_suggestion_source,
                            matched_term=candidate_context.current_role if role_suggestion_source == "verified_professional_experience" else professional_domain,
                            matched_against=role,
                            confidence=0.5,
                        )
                    ],
                    missing_requirements=["No active vacancy matches this domain profile"],
                )
                for role in suitable_roles[:3]
            ]

        # Hierarchy-constrained organization classification: MainDept -> Dept -> Desig
        hierarchy_res = candidate_context.cand_hierarchy or DynamicTaxonomyService.classify_organization_hierarchy(
            role_or_summary=candidate_context.current_role or professional_domain or recommended_dept,
            skills=candidate_context.professional_skills,
            domain=professional_domain,
            experience_years=candidate_context.candidate_experience,
            cv_text=cv_text,
        )
        main_dept_res = DynamicTaxonomyService.classify_main_department(
            role_or_summary=candidate_context.current_role or professional_domain or recommended_dept,
            skills=candidate_context.professional_skills,
            domain=professional_domain,
            experience_years=candidate_context.candidate_experience,
            cv_text=cv_text,
        )

        if not has_genuine_match:
            top_level_match_status = MatchStatus.PARTIAL_MATCH if has_potential_match else MatchStatus.NO_SUITABLE_MATCH
            if cand_classification:
                cand_classification = cand_classification.model_copy(update={
                    "match_status": MatchStatus.NO_SUITABLE_MATCH,
                    "industry_department": cand_classification.industry_department or recommended_dept or None,
                    "industry_domain": cand_classification.industry_domain or professional_domain or None,
                    "db_main_department_id": hierarchy_res.main_department.id,
                    "db_main_department_name": hierarchy_res.main_department.name,
                    "db_department_id": hierarchy_res.department.id,
                    "db_department_name": hierarchy_res.department.name,
                    "db_designation_id": hierarchy_res.designation.id,
                    "db_designation_name": hierarchy_res.designation.name,
                    "main_department_classification": main_dept_res,
                    "hierarchy_classification": hierarchy_res,
                })
        else:
            top_level_match_status = MatchStatus.DB_MATCH
            if cand_classification:
                cand_classification = cand_classification.model_copy(update={
                    "db_main_department_id": hierarchy_res.main_department.id or cand_classification.db_main_department_id,
                    "db_main_department_name": hierarchy_res.main_department.name or cand_classification.db_main_department_name,
                    "db_department_id": hierarchy_res.department.id or cand_classification.db_department_id,
                    "db_department_name": hierarchy_res.department.name or cand_classification.db_department_name,
                    "db_designation_id": hierarchy_res.designation.id or cand_classification.db_designation_id,
                    "db_designation_name": hierarchy_res.designation.name or cand_classification.db_designation_name,
                    "main_department_classification": main_dept_res,
                    "hierarchy_classification": hierarchy_res,
                })

        quality_gate.record(
            "final_classification",
            "PASSED",
            match_status=top_level_match_status.value,
            best_vacancy_id=best_match.vacancy_id if best_match else None,
            final_score=best_match.vacancy_fit_score if best_match else None,
        )

        from app.services.experience_gap_service import ExperienceGapService
        gap_analysis = ExperienceGapService.analyze_timeline(resume_json or {}, cv_text)

        result = EnrichedCandidateAnalysis(
            analysis_run_id=analysis_run_id,
            analysis_version=analysis_run_id,
            match_status=top_level_match_status,
            primary_department=recommended_dept,
            recommended_department=recommended_dept,
            professional_domain=professional_domain,
            strengths=strengths,
            suitable_job_roles=suitable_roles,
            has_genuine_match=has_genuine_match,
            active_vacancy_summary=active_vacancy_summary,
            scoring_profile_code=scoring_config.profile_code,
            scoring_profile_version=scoring_config.profile_version,
            config_version=RuleConfigManager.get_config().version,
            prompt_version=settings.OPTIMIZED_PROMPT_VERSION,
            ai_career_summary=ai_career_summary,
            best_match=best_match,
            suitable_openings=suitable_matches,
            unsuitable_openings=unsuitable_matches,
            llm_skipped=llm_skipped,
            normalized_resume=normalized_resume,
            classification=cand_classification,
            main_department_classification=main_dept_res,
            ai_career_suggestions=ai_career_suggestions,
            experience_gap_analysis=gap_analysis,
            freshness_status=vacancy_freshness,
            source_watermark=vacancy_version,
            quality_metadata={
                "matching_version": settings.MATCHING_VERSION,
                "model_identifier_hash": hashlib.sha256(settings.OLLAMA_MODEL.encode("utf-8")).hexdigest(),
                "grounding_ratio": round(grounding_report.ratio, 4),
                "grounded_assertions": grounding_report.grounded_assertions,
                "grounding_assertions": grounding_report.assertions,
                "invalid_vacancy_ids_removed": len(grounding_report.invalid_vacancy_ids),
                "missing_llm_vacancy_ids": len(grounding_report.missing_vacancy_ids),
                "unsupported_claims_removed": len(grounding_report.unsupported_claims),
                "quality_shadow_mode": settings.LLM_SHADOW_QUALITY_ENABLED,
                "quality_gate": quality_gate.as_dict(),
                "rule_version": rule_version,
                "taxonomy_version": taxonomy_version,
                "hiring_risk_prompt_version": hiring_risk_prompt_version,
                "hiring_risk_prompt_identity": hiring_risk_prompt_identity,
                "hiring_risk_policy_version": hiring_risk_policy_version,
                "llm_lineage": {
                    "raw_vacancy_count": len(raw_llm_lineage),
                    "grounded_vacancy_count": len(grounded_llm_lineage),
                    "raw_requirement_count": sum(item.get("requirements", 0) for item in raw_llm_lineage.values()),
                    "grounded_requirement_count": sum(item.get("requirements", 0) for item in grounded_llm_lineage.values()),
                    "raw_evidence_count": sum(item.get("evidence", 0) for item in raw_llm_lineage.values()),
                    "grounded_evidence_count": sum(item.get("evidence", 0) for item in grounded_llm_lineage.values()),
                },
            },
        )

        MatchService._enqueue_shadow_if_requested(
            result,
            source_candidate_id=source_candidate_id,
            cv_text=cv_text,
            shadow_run=_shadow_run,
        )

        # Cache the match result for instant repeat searches if worker generation is current
        from app.repositories.result import ResultRepository
        cv_key_stem = str(cv_key or document_hash)
        if ResultRepository.is_generation_current(cv_key_stem, incoming_generation="", resource="match_result"):
            match_result_cache_manager.set(match_cache_key, result.model_dump())
            CacheIndex.add("match_by_doc", document_hash, match_cache_key)
            if cv_key:
                CacheIndex.add("match_by_cand", cv_key, match_cache_key)
            logger.info(f"[MATCH_CACHE_SET] Cached match result for doc={document_hash[:12]}...")
        else:
            logger.warning(f"[STALE_GENERATION_WRITE_REJECTED] resource=match_result doc={document_hash[:12]}")
        return result

    @staticmethod
    def _unavailable_analysis(
        normalized_resume: NormalizedResume,
        readiness: MatchingReadiness,
        quality_gate: MatchingQualityGate,
        status: MatchStatus = MatchStatus.ANALYSIS_UNAVAILABLE,
    ) -> EnrichedCandidateAnalysis:
        quality_gate.record("final_classification", "BLOCKED", reason_code=readiness.reason_code)
        try:
            config_version = RuleConfigManager.get_config().version
        except Exception:
            config_version = None
        return EnrichedCandidateAnalysis(
            analysis_run_id=get_analysis_run_id(),
            analysis_version=get_analysis_run_id(),
            status=status.value,
            stage="matching_quality_gate",
            match_status=status,
            has_genuine_match=False,
            active_vacancy_summary=f"{status.value}: {readiness.reason}",
            suitable_openings=[],
            unsuitable_openings=[],
            normalized_resume=normalized_resume,
            config_version=config_version,
            prompt_version=settings.OPTIMIZED_PROMPT_VERSION,
            quality_metadata={
                "matching_version": settings.MATCHING_VERSION,
                "unavailable_reason_code": readiness.reason_code,
                "quality_gate": quality_gate.as_dict(),
            },
        )

    @staticmethod
    def _enqueue_shadow_if_requested(
        result: EnrichedCandidateAnalysis,
        *,
        source_candidate_id: int | None,
        cv_text: str,
        shadow_run: bool,
    ) -> None:
        if not settings.SHADOW_MODE_ENABLED or source_candidate_id is None or shadow_run:
            return

        from app.services.shadow_validation_service import ShadowValidationService

        vacancy_id = result.best_match.vacancy_id if result.best_match else None
        try:
            numeric_vacancy_id = int(vacancy_id) if vacancy_id else None
        except (TypeError, ValueError):
            logger.warning(f"Could not enqueue shadow validation for non-numeric vacancy_id: {vacancy_id}")
            result.quality_metadata["shadow_validation_status"] = "not_queued_invalid_vacancy_id"
            return

        queued = ShadowValidationService.enqueue_shadow_validation(
            source_candidate_id=source_candidate_id,
            vacancy_id=numeric_vacancy_id,
            prod_result_dict=result.model_dump(),
            cv_text=cv_text,
        )
        result.quality_metadata["shadow_validation_status"] = "queued" if queued else "not_queued"

    @staticmethod
    def _empty_job_match() -> EnrichedJobMatchResult:
        return EnrichedJobMatchResult(
            job_id="",
            job_title="",
            department="",
            vacancy_id=None,
            job_profile_id=None,
            company_id=None,
            department_id=None,
            department_name="",
            location_id=None,
            score=0.0,
            overall_score=0.0,
            role_score=0.0,
            skills_score=0.0,
            experience_score=0.0,
            education_score=0.0,
            domain_score=0.0,
            technology_score=0.0,
            certification_score=0.0,
            responsibilities_score=0.0,
            coverage=1.0,
            ranking_reason="",
            classification="LOW",
            recommendation="HR review required.",
            matched_skills=[],
            missing_skills=[],
            matched_keywords=[],
            missing_keywords=[],
            llm_reason="",
            inferred_skills=[],
        )

    @staticmethod
    def _empty_analysis(
        cv_text: str = "",
        normalized_resume: NormalizedResume | None = None,
        quality_gate: MatchingQualityGate | None = None,
        is_global_empty: bool = False,
    ) -> EnrichedCandidateAnalysis:
        from app.schemas.scoring_config import ScoringConfig

        scoring_config = ScoringConfig.load()
        cand_profile = ScoringEngine.extract_candidate_domain_profile(cv_text=cv_text) if cv_text else {}
        industry_dept = cand_profile.get("recommended_department", "")
        industry_domain = cand_profile.get("professional_domain", "")
        strengths = cand_profile.get("strengths", [])
        roles = cand_profile.get("suitable_job_roles", [])
        if not roles and normalized_resume and normalized_resume.employment:
            current_title = normalized_resume.employment[0].job_title.normalized_value
            roles = CandidateDomainService.validate_job_roles([current_title], cv_text) if current_title else []
        best_match = None
        ai_career_suggestions = [
            AISuggestion(
                suggested_role=role,
                suggested_domain=industry_domain,
                confidence=0.5,
                evidence=[
                    ClassificationEvidence(
                        source="verified_professional_experience" if normalized_resume and normalized_resume.employment else "candidate_domain_profile",
                        matched_term=role if normalized_resume and normalized_resume.employment else industry_domain,
                        matched_against=role,
                        confidence=0.5,
                    )
                ],
                missing_requirements=["No eligible active vacancy is available"],
            )
            for role in roles[:3]
        ]

        from app.services.experience_gap_service import ExperienceGapService
        gap_analysis = ExperienceGapService.analyze_timeline({}, cv_text)

        hierarchy_res = DynamicTaxonomyService.classify_organization_hierarchy(
            role_or_summary=roles[0] if roles else industry_dept,
            skills=[],
            domain=industry_domain,
            cv_text=cv_text,
        )

        main_dept_res = DynamicTaxonomyService.classify_main_department(
            role_or_summary=roles[0] if roles else industry_dept,
            skills=[],
            domain=industry_domain,
            cv_text=cv_text,
        )

        status = MatchStatus.NO_ACTIVE_VACANCIES if is_global_empty else MatchStatus.NO_SUITABLE_MATCH
        summary = "NO_ACTIVE_VACANCIES: No active vacancies available in system for evaluation." if is_global_empty else "NO_SUITABLE_MATCH: No compatible active vacancies found for this candidate profile."
        
        return EnrichedCandidateAnalysis(
            analysis_run_id=get_analysis_run_id(),
            analysis_version=get_analysis_run_id(),
            match_status=status,
            primary_department=industry_dept or None,
            recommended_department=industry_dept or None,
            professional_domain=industry_domain or None,
            strengths=strengths,
            suitable_job_roles=roles,
            has_genuine_match=False,
            active_vacancy_summary=summary,
            scoring_profile_code=scoring_config.profile_code,
            scoring_profile_version=scoring_config.profile_version,
            config_version=RuleConfigManager.get_config().version,
            prompt_version=settings.OPTIMIZED_PROMPT_VERSION,
            ai_career_summary=(
                f"Candidate Profile Analysis:\n"
                f"• Industry Department: {industry_dept}\n"
                f"• Industry Domain: {industry_domain}\n"
                f"• Key Strengths: {'; '.join(strengths)}\n"
                f"• Suitable Job Roles: {', '.join(roles)}"
            ),
            best_match=best_match,
            suitable_openings=[],
            normalized_resume=normalized_resume,
            main_department_classification=main_dept_res,
            hierarchy_classification=hierarchy_res,
            ai_career_suggestions=ai_career_suggestions,
            experience_gap_analysis=gap_analysis,
            quality_metadata={
                "matching_version": settings.MATCHING_VERSION,
                "quality_gate": quality_gate.as_dict() if quality_gate else {},
            },
        )

    @staticmethod
    async def analyze_from_result_file(result_json_path: str | Path) -> dict[str, Any]:
        source_data = ResultRepository.read_result(result_json_path)
        candidate_key = str(source_data.get("id") or source_data.get("scan_id") or Path(result_json_path).stem)
        data = ResultRepository.resolve_result(candidate_key) or source_data

        cv_text = data.get("markdown")
        if not cv_text:
            raise ValueError("No markdown text found in the result file.")

        cv_hash = data.get("cv_hash", "")
        cv_key = str(data.get("id") or data.get("scan_id") or Path(result_json_path).stem)
        source_candidate_id = data.get("source_candidate_id")
        stored_normalized_resume = NormalizedResume.model_validate(data["normalized_resume"]) if data.get("normalized_resume") else None
        enriched_analysis = await MatchService.analyze_single_cv(
            cv_text,
            document_hash=cv_hash,
            cv_key=cv_key,
            source_candidate_id=source_candidate_id,
            resume_json=data.get("resume_json"),
            normalized_resume=stored_normalized_resume,
            deterministic_experience=(stored_normalized_resume.experience.authoritative_years if stored_normalized_resume else ((data.get("quality_metrics") or {}).get("experience_years") or None)),
            force_reanalysis=True,
        )

        analysis_payload = enriched_analysis.model_dump()
        data["match_analysis"] = analysis_payload
        data["enriched_match_analysis"] = analysis_payload
        data["analysis_run_id"] = get_analysis_run_id()
        data["analysis_version"] = data["analysis_run_id"]

        canonical_filename = ResultRepository.canonical_filename(data, result_json_path)
        ResultRepository.atomic_save_result(canonical_filename, data)
        logger.info(
            f"analysis_run_id={data['analysis_run_id']} candidate={cv_key} canonical_result_updated=true "
            f"candidate_api_result_version={data['analysis_version']}"
        )
        return data
