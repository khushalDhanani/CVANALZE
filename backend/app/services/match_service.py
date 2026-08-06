from __future__ import annotations
import asyncio
import hashlib
from pathlib import Path
from typing import Any, cast

from app.core.cache import CacheIndex, CacheKey, match_result_cache_manager
from app.core.config import settings
from app.core.logging import logger
from app.core.profiler import PipelineProfiler
from app.core.rule_config_manager import RuleConfigManager
from app.prompts.optimized_match import build_optimized_match_prompt
from app.repositories.config import ConfigRepository
from app.repositories.job import JobRepository
from app.repositories.llm_cache import LLMCacheRepository
from app.repositories.result import ResultRepository
from app.schemas.analysis import EnrichedCandidateAnalysis, EnrichedJobMatchResult
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.classification_types import AISuggestion, ClassificationEvidence, NormalizedClassification
from app.schemas.job_context import JobEvaluationContext
from app.schemas.normalized_resume import NormalizedResume
from app.services.document_parser import ResumeJsonExtractor
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
from app.services.llm_service import OllamaLLMService
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
        upload_ms: float = 0.0,
        docling_extraction_ms: float = 0.0,
        cv_embedding: list[float] | None = None,
        resume_json: dict[str, Any] | None = None,
        normalized_resume: NormalizedResume | None = None,
        deterministic_experience: float | None = None,
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
        candidate_id = str(candidate_id).strip() if candidate_id else ""
        extraction_version = f"{settings.EXTRACTION_PARSER_VERSION}:{settings.EXTRACTION_SCHEMA_VERSION}"

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

        if deterministic_experience is None:
            deterministic_experience = normalized_resume.experience.deterministic_years

        from fastapi.concurrency import run_in_threadpool

        # 3. Vacancy retrieval
        with profiler.time_stage("vacancy_retrieval"):
            openings = job_openings if job_openings is not None else await run_in_threadpool(JobRepository.get_all_jobs)

        if not openings:
            logger.warning("MatchService.analyze_single_cv: No job openings available for matching.")
            profiler.finish()
            profiler.log_summary()
            return MatchService._empty_analysis(normalized_resume=normalized_resume)

        profiler.metrics.vacancies_before_filtering = len(openings)

        vacancy_ids = sorted(str(job.get("vacancy_id") or job.get("id") or "") for job in openings if job.get("vacancy_id") is not None or job.get("id") is not None)
        vacancy_version = JobRepository.compute_matching_vacancy_version(openings)

        # 4. Match Result Cache Check (instant repeat searches)
        t_cache_start = asyncio.get_event_loop().time()
        match_cache_key = CacheKey.for_match_result(
            document_hash=document_hash,
            candidate_id=candidate_id,
            vacancy_version=vacancy_version,
            vacancy_ids=vacancy_ids,
            prompt_version=settings.OPTIMIZED_PROMPT_VERSION,
            model_version=settings.OLLAMA_MODEL,
            extraction_version=extraction_version,
            matching_version=settings.MATCHING_VERSION,
        ).to_key()

        cached_result = match_result_cache_manager.get(match_cache_key)
        if cached_result is not None:
            logger.info(f"[MATCH_CACHE_HIT] Returning cached match result for doc={document_hash[:12]}...")
            profiler.metrics.cache_hit = True
            profiler.metrics.cache_lookup_ms = round((asyncio.get_event_loop().time() - t_cache_start) * 1000.0, 2)
            profiler.finish()
            profiler.log_summary()
            return EnrichedCandidateAnalysis.model_validate(cached_result)
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

        # 5. Python Pre-filter stage (Stage 0 Taxonomy + Stage 1 Vector + Stage 2 RRF)
        with profiler.time_stage("prefilter"):
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
        filtered_vacancies = [job.raw_job for job in filtered_job_contexts]
        profiler.metrics.vacancies_after_filtering = len(filtered_job_contexts)

        from app.schemas.scoring_config import ScoringConfig
        scoring_config = ScoringConfig.load()

        # CONFIDENCE GATE CHECK (Phase 3)
        llm_skipped = False
        if filtered_job_contexts:
            pre_llm_matches = []
            for job_context in filtered_job_contexts:
                try:
                    pre_llm_match = ScoringEngine.evaluate_job_match(
                        cv_text=cv_text,
                        job=job_context,
                        llm_match=None,
                        scoring_config=scoring_config,
                        context=candidate_context,
                    )
                    pre_llm_matches.append(pre_llm_match)
                except Exception as e:
                    logger.error(f"Error in rule-based matching for job {job_context.job_id}: {e}")

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

        if not llm_skipped:
            # 4. Prompt Construction & Token Count
            with profiler.time_stage("prompt_construction"):
                prompt, token_est, char_count = build_optimized_match_prompt(cv_text, filtered_vacancies)
                profiler.metrics.token_count = token_est
                profiler.metrics.context_char_count = char_count

            # Compute version-aware cache key
            filtered_vacancy_ids = [str(j.get("vacancy_id") or j.get("id")) for j in filtered_vacancies]
            cache_key = LLMCacheRepository.compute_composite_hash(
                document_hash=document_hash,
                candidate_id=candidate_id,
                vacancy_ids=filtered_vacancy_ids,
                vacancy_version=vacancy_version,
                prompt_version=settings.OPTIMIZED_PROMPT_VERSION,
                model_version=settings.OLLAMA_MODEL,
                extraction_version=extraction_version,
                matching_version=settings.MATCHING_VERSION,
            )

            # 5. Single Optimized LLM Call + Pydantic Validation (with cache check & retries)
            optimized_response = await asyncio.to_thread(
                OllamaLLMService.run_optimized_match,
                prompt,
                settings.OPTIMIZED_PROMPT_VERSION,
                cache_key,
                profiler,
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
                    )

                    # Wrap into EnrichedJobMatchResult
                    llm_reason = llm_match.semantic_reason if llm_match else ""
                    inferred_skills = llm_match.inferred_skills if llm_match else (optimized_profile.inferred_skills if optimized_profile else [])

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
                        reason=job_match.reason or llm_reason,
                        career_transition_detected=job_match.career_transition_detected,
                        career_transition_note=job_match.career_transition_note,
                        llm_reason=llm_reason,
                        inferred_skills=inferred_skills,
                    )
                    evaluated_matches.append(enriched_match)
                except Exception as e:
                    logger.error(f"Error in LLM-enriched matching for job {job.get('id') or job.get('vacancy_id')}: {e}")

            evaluated_matches.sort(key=lambda m: m.score, reverse=True)

            if evaluated_matches:
                logger.debug("MATCHING PIPELINE DEBUG OUTPUT")
                for i, m in enumerate(evaluated_matches):
                    if i == 0:
                        m.ranking_reason = f"Ranked #1 with highest verified score of {m.score}%."
                    else:
                        m.ranking_reason = f"Ranked #{i + 1} due to lower score ({m.score}% vs top {evaluated_matches[0].score}%)."

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

        has_genuine_match = False
        if evaluated_matches and evaluated_matches[0].score >= RuleConfigManager.get_match_rules().scoring_parameters.match_medium_threshold:
            top_m = evaluated_matches[0]
            has_domain_mismatch = any(f.requirement_id == "req_domain_mismatch" for f in top_m.mandatory_failures)
            if not has_domain_mismatch:
                has_genuine_match = True

        if has_genuine_match and evaluated_matches:
            top_m = evaluated_matches[0]
            skills_str = ", ".join(top_m.matched_skills[:4]) if top_m.matched_skills else "core qualification requirements"
            active_vacancy_summary = (
                f"Genuine Match Found: Candidate is a strong match for '{top_m.job_title}' "
                f"in the {top_m.department_name or top_m.department} department "
                f"with an overall match score of {top_m.score}%. Key matching skills include {skills_str}."
            )
            best_match = top_m
        else:
            active_vacancy_summary = f"No suitable active vacancy found matching candidate domain/taxonomy profile (Primary Domain: {professional_domain}). Manual HR review recommended."
            best_match = evaluated_matches[0] if evaluated_matches else None

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

        logger.info(f"Candidate Domain Analysis: dept='{recommended_dept}', domain='{professional_domain}', has_genuine_match={has_genuine_match}")

        # Split evaluated matches into suitable (HIGH/MEDIUM) vs unsuitable (LOW)
        suitable_matches = [m for m in evaluated_matches if m.classification in ("HIGH", "MEDIUM")]
        unsuitable_matches = [m for m in evaluated_matches if m.classification not in ("HIGH", "MEDIUM")]

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

        if not has_genuine_match and suitable_roles:
            ai_career_suggestions = [
                AISuggestion(
                    suggested_role=role,
                    suggested_domain=professional_domain,
                    confidence=0.5,
                    evidence=[
                        ClassificationEvidence(
                            source="candidate_domain_profile",
                            matched_term=professional_domain,
                            matched_against=role,
                            confidence=0.5,
                        )
                    ],
                    missing_requirements=["No active vacancy matches this domain profile"],
                )
                for role in suitable_roles[:3]
            ]
            
        from app.schemas.classification_types import MatchStatus

        if has_genuine_match:
            top_level_match_status = MatchStatus.DB_MATCH
        elif cand_classification and cand_classification.match_status == "DB_MATCH":
            top_level_match_status = MatchStatus.PARTIAL_MATCH
        else:
            top_level_match_status = MatchStatus.NO_SUITABLE_MATCH

        result = EnrichedCandidateAnalysis(
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
            ai_career_suggestions=ai_career_suggestions,
        )

        # Cache the match result for instant repeat searches
        match_result_cache_manager.set(match_cache_key, result.model_dump())
        CacheIndex.add("match_by_doc", document_hash, match_cache_key)
        if candidate_id:
            CacheIndex.add("match_by_cand", candidate_id, match_cache_key)
        logger.info(f"[MATCH_CACHE_SET] Cached match result for doc={document_hash[:12]}...")

        return result

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
    ) -> EnrichedCandidateAnalysis:
        cand_profile = ScoringEngine.extract_candidate_domain_profile(cv_text=cv_text) if cv_text else {}
        rec_dept = cand_profile.get("recommended_department", "")
        prof_domain = cand_profile.get("professional_domain", "")
        strengths = cand_profile.get("strengths", [])
        roles = cand_profile.get("suitable_job_roles", [])
        best_match = None

        return EnrichedCandidateAnalysis(
            primary_department=rec_dept,
            recommended_department=rec_dept,
            professional_domain=prof_domain,
            strengths=strengths,
            suitable_job_roles=roles,
            has_genuine_match=False,
            active_vacancy_summary="No suitable active vacancy found.",
            scoring_profile_code=scoring_config.profile_code if 'scoring_config' in locals() else None,
            scoring_profile_version=scoring_config.profile_version if 'scoring_config' in locals() else None,
            config_version=RuleConfigManager.get_config().version,
            prompt_version=settings.OPTIMIZED_PROMPT_VERSION,
            ai_career_summary=(
                f"Candidate Profile Analysis:\n"
                f"• Recommended Department: {rec_dept}\n"
                f"• Professional Domain: {prof_domain}\n"
                f"• Key Strengths: {'; '.join(strengths)}\n"
                f"• Suitable Job Roles: {', '.join(roles)}"
            ),
            best_match=best_match,
            suitable_openings=[],
            normalized_resume=normalized_resume,
        )

    @staticmethod
    async def analyze_from_result_file(result_json_path: str | Path) -> dict[str, Any]:
        data = ResultRepository.read_result(result_json_path)

        cv_text = data.get("markdown")
        if not cv_text:
            raise ValueError("No markdown text found in the result file.")

        cv_hash = data.get("cv_hash", "")
        cand_id = data.get("candidate_id", "")
        stored_normalized_resume = NormalizedResume.model_validate(data["normalized_resume"]) if data.get("normalized_resume") else None
        enriched_analysis = await MatchService.analyze_single_cv(
            cv_text,
            document_hash=cv_hash,
            candidate_id=cand_id,
            resume_json=data.get("resume_json"),
            normalized_resume=stored_normalized_resume,
            deterministic_experience=(stored_normalized_resume.experience.deterministic_years if stored_normalized_resume else ((data.get("quality_metrics") or {}).get("experience_years") or None)),
        )

        # Merge back into data
        data["enriched_match_analysis"] = enriched_analysis.model_dump()

        # Save back or save as new
        path = Path(result_json_path)
        new_filename = f"{path.stem}_enriched.json"

        new_path = ResultRepository.save_result(new_filename, data)

        data["enriched_result_file_path"] = str(new_path)
        return data
