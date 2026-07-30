import asyncio
import re
from pathlib import Path
from typing import Any

from app.core.cache import CacheIndex, CacheKey, match_result_cache_manager
from app.core.config import settings
from app.core.logging import logger
from app.core.profiler import PipelineProfiler
from app.prompts.optimized_match import build_optimized_match_prompt
from app.repositories.job import JobRepository
from app.repositories.llm_cache import LLMCacheRepository
from app.repositories.result import ResultRepository
from app.schemas.analysis import EnrichedCandidateAnalysis, EnrichedJobMatchResult
from app.services.llm_service import OllamaLLMService
from app.services.scoring_engine import ScoringEngine
from app.services.vacancy_prefilter import VacancyPreFilter


class MatchService:
    @classmethod
    def _find_relevant_department_vacancies(cls, cv_text: str, openings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[int]]:
        """
        Dynamically narrows active vacancies to relevant department vacancies by matching
        candidate CV against active department names and job titles.
        """
        cv_lower = cv_text.lower()
        dept_map = {}

        for job in openings:
            dept_id = job.get("department_id")
            dept_name = job.get("department_name") or job.get("department") or "Unknown Department"
            if dept_id is None:
                continue

            if dept_id not in dept_map:
                dept_map[dept_id] = {
                    "dept_id": dept_id,
                    "dept_name": dept_name,
                    "vacancies": [],
                    "score": 0.0
                }
            dept_map[dept_id]["vacancies"].append(job)

            title = job.get("title", "").lower()
            title_terms = [t for t in re.split(r"[\s/&()\-,]+", title) if len(t) > 2 and t not in {"and", "team", "for", "the", "with"}]
            matched_terms = [t for t in title_terms if t in cv_lower]

            score = len(matched_terms) * 10.0
            if dept_name.lower() in cv_lower:
                score += 30.0

            dept_map[dept_id]["score"] += score

        relevant_depts = [d for d in dept_map.values() if d["score"] > 0]
        relevant_depts.sort(key=lambda d: d["score"], reverse=True)
        relevant_depts = relevant_depts[:3]

        if not relevant_depts:
            dept_names = list({d["dept_name"] for d in dept_map.values()})
            dept_ids = sorted(dept_map.keys())
            return openings, dept_names, dept_ids

        narrowed_vacancies = []
        for d in relevant_depts:
            narrowed_vacancies.extend(d["vacancies"])

        for job in narrowed_vacancies:
            title = job.get("title", "").lower()
            title_terms = [t for t in re.split(r"[\s/&()\-,]+", title) if len(t) > 2 and t not in {"and", "team", "for", "the", "with"}]
            matched_terms = [t for t in title_terms if t in cv_lower]
            job["_temp_rel"] = len(matched_terms)

        narrowed_vacancies.sort(key=lambda j: j.get("_temp_rel", 0), reverse=True)
        narrowed_vacancies = narrowed_vacancies[:10]

        dept_names = [d["dept_name"] for d in relevant_depts]
        dept_ids = [d["dept_id"] for d in relevant_depts]
        return narrowed_vacancies, dept_names, dept_ids

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
    ) -> EnrichedCandidateAnalysis:
        profiler = PipelineProfiler()
        profiler.metrics.upload_ms = upload_ms
        profiler.metrics.docling_extraction_ms = docling_extraction_ms

        # 1. Validate CV text is meaningful (not just image markers from failed OCR)
        if not cv_text or not cv_text.strip():
            raise ValueError("CV text content cannot be empty.")

        cv_stripped = cv_text.strip()
        if "<!-- image -->" in cv_stripped and len(cv_stripped) < 50:
            raise ValueError(
                "CV document is a scanned image with no extractable text. "
                "OCR could not extract any meaningful content."
            )

        # 2. Match Result Cache Check (instant repeat searches)
        t_cache_start = asyncio.get_event_loop().time()
        vacancy_version = JobRepository.get_vacancy_version()
        match_cache_key = CacheKey.for_match_result(
            document_hash=document_hash,
            candidate_id=candidate_id,
            vacancy_version=vacancy_version,
            prompt_version=settings.OPTIMIZED_PROMPT_VERSION,
            matching_version=settings.MATCHING_VERSION,
        ).to_key()

        if match_cache_key:
            cached_result = match_result_cache_manager.get(match_cache_key)
            if cached_result is not None:
                logger.info(f"[MATCH_CACHE_HIT] Returning cached match result for doc={document_hash[:12]}...")
                profiler.metrics.cache_hit = True
                profiler.metrics.cache_lookup_ms = round((asyncio.get_event_loop().time() - t_cache_start) * 1000.0, 2)
                profiler.finish()
                profiler.log_summary()
                return EnrichedCandidateAnalysis.model_validate(cached_result)
        profiler.metrics.cache_lookup_ms = round((asyncio.get_event_loop().time() - t_cache_start) * 1000.0, 2)

        # 3. JSON Loading stage timing (parsing CV text input)
        with profiler.time_stage("resume_json"):
            _ = cv_text.strip()

        from fastapi.concurrency import run_in_threadpool
        # 2. Vacancy retrieval
        with profiler.time_stage("vacancy_retrieval"):
            openings = (
                job_openings if job_openings is not None else await run_in_threadpool(JobRepository.get_all_jobs)
            )

        if not openings:
            logger.warning("MatchService.analyze_single_cv: No job openings available for matching.")
            profiler.finish()
            profiler.log_summary()
            return MatchService._empty_analysis()

        profiler.metrics.vacancies_before_filtering = len(openings)

        # 3. Python Pre-filter stage
        with profiler.time_stage("prefilter"):
            filtered_vacancies = VacancyPreFilter.filter_vacancies(
                cv_text=cv_text,
                openings=openings,
                candidate_experience=candidate_experience,
                top_k=settings.PREFILTER_TOP_K,
                cv_embedding=cv_embedding,
            )
        profiler.metrics.vacancies_after_filtering = len(filtered_vacancies)

        # CONFIDENCE GATE CHECK (Phase 3)
        llm_skipped = False
        if filtered_vacancies:
            pre_llm_matches = []
            for job in filtered_vacancies:
                pre_llm_match = ScoringEngine.evaluate_job_match(
                    cv_text=cv_text,
                    job=job,
                    candidate_experience=candidate_experience,
                    candidate_ctc=candidate_ctc,
                    optimized_profile=None,
                    llm_match=None,
                )
                pre_llm_matches.append(pre_llm_match)
                
            pre_llm_matches.sort(key=lambda m: m.score, reverse=True)
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
                prompt, token_est, char_count = build_optimized_match_prompt(
                    cv_text, filtered_vacancies
                )
                profiler.metrics.token_count = token_est
                profiler.metrics.context_char_count = char_count

            # Compute version-aware cache key
            vacancy_ids = [str(j.get("vacancy_id") or j.get("id")) for j in filtered_vacancies]
            cache_key = LLMCacheRepository.compute_composite_hash(
                document_hash=document_hash,
                candidate_id=candidate_id,
                vacancy_ids=vacancy_ids,
                prompt_version=settings.OPTIMIZED_PROMPT_VERSION,
                model_version=settings.OLLAMA_MODEL,
                matching_version=settings.OPTIMIZED_PROMPT_VERSION,
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
            if optimized_response:
                for vm in optimized_response.matched_vacancies:
                    llm_matches_map[str(vm.vacancy_id)] = vm

        # 6. Deterministic Scoring & Ranking in Python
        evaluated_matches = []
        with profiler.time_stage("scoring"):
            for job in filtered_vacancies:
                vac_id_str = str(job.get("vacancy_id") or job.get("id"))
                llm_match = llm_matches_map.get(vac_id_str)

                job_match = ScoringEngine.evaluate_job_match(
                    cv_text=cv_text,
                    job=job,
                    candidate_experience=candidate_experience,
                    candidate_ctc=candidate_ctc,
                    optimized_profile=optimized_profile,
                    llm_match=llm_match,
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


            evaluated_matches.sort(key=lambda m: m.score, reverse=True)

            if evaluated_matches:
                print("\n" + "="*60)
                print("🏆 MATCHING PIPELINE DEBUG OUTPUT")
                print("="*60)
                for i, m in enumerate(evaluated_matches):
                    if i == 0:
                        m.ranking_reason = f"Ranked #1 with highest verified score of {m.score}%."
                    else:
                        m.ranking_reason = f"Ranked #{i+1} due to lower score ({m.score}% vs top {evaluated_matches[0].score}%)."
                    
                    evidence_snippet = "; ".join(f"{ev.cv_evidence}" for ev in m.evidence.values())
                    if len(evidence_snippet) > 150:
                        evidence_snippet = evidence_snippet[:147] + "..."
                    if not evidence_snippet:
                        evidence_snippet = "None"
                    
                    fails_snippet = "; ".join(f"{f.description}" for f in m.mandatory_failures) if m.mandatory_failures else "None"
                    
                    print(f"[VACANCY] ID: {m.vacancy_id} | Title: {m.job_title}")
                    print(f" -> Overall Score: {m.score}% (Coverage: {int(m.coverage * 100)}%)")
                    print(f" -> SubScores: Role={m.role_score}, Skills={m.skills_score}, Exp={m.experience_score}, Edu={m.education_score}, Domain={m.domain_score}, Tech={m.technology_score}")
                    print(f" -> Mandatory Fails: {fails_snippet}")
                    print(f" -> Evidence: {evidence_snippet}")
                    print(f" -> Ranking Reason: {m.ranking_reason}")
                    print("-" * 60)
                print()

        profiler.finish()
        profiler.log_summary()

        cand_profile = ScoringEngine.extract_candidate_domain_profile(
            cv_text=cv_text,
            optimized_profile=optimized_profile,
        )
        recommended_dept = cand_profile.get("recommended_department", "General")
        professional_domain = cand_profile.get("professional_domain", "General Operations")
        strengths = cand_profile.get("strengths", [])
        suitable_roles = cand_profile.get("suitable_job_roles", [])

        has_genuine_match = False
        if evaluated_matches and evaluated_matches[0].score >= settings.MATCH_MEDIUM_THRESHOLD:
            top_m = evaluated_matches[0]
            has_domain_mismatch = any(
                f.requirement_id == "req_domain_mismatch" for f in top_m.mandatory_failures
            )
            if not has_domain_mismatch:
                has_genuine_match = True

        if has_genuine_match and evaluated_matches:
            top_m = evaluated_matches[0]
            skills_str = (
                ", ".join(top_m.matched_skills[:4])
                if top_m.matched_skills
                else "core qualification requirements"
            )
            active_vacancy_summary = (
                f"Genuine Match Found: Candidate is a strong match for '{top_m.job_title}' "
                f"in the {top_m.department_name or top_m.department} department "
                f"with an overall match score of {top_m.score}%. Key matching skills include {skills_str}."
            )
            best_match = top_m
        else:
            active_vacancy_summary = "No suitable active vacancy found."
            best_match = evaluated_matches[0] if evaluated_matches else MatchService._empty_job_match()

        roles_str = ", ".join(suitable_roles) if suitable_roles else "General Roles"
        strengths_str = "; ".join(strengths) if strengths else "Solid technical and professional baseline."

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

        logger.info(
            f"Candidate Domain Analysis: dept='{recommended_dept}', domain='{professional_domain}', "
            f"has_genuine_match={has_genuine_match}"
        )

        result = EnrichedCandidateAnalysis(
            primary_department=recommended_dept,
            recommended_department=recommended_dept,
            professional_domain=professional_domain,
            strengths=strengths,
            suitable_job_roles=suitable_roles,
            has_genuine_match=has_genuine_match,
            active_vacancy_summary=active_vacancy_summary,
            ai_career_summary=ai_career_summary,
            best_match=best_match,
            suitable_openings=evaluated_matches,
            llm_skipped=llm_skipped,
        )

        # Cache the match result for instant repeat searches
        if match_cache_key:
            match_result_cache_manager.set(match_cache_key, result.model_dump())
            CacheIndex.add("match_by_doc", document_hash, match_cache_key)
            if candidate_id:
                CacheIndex.add("match_by_cand", candidate_id, match_cache_key)
            logger.info(f"[MATCH_CACHE_SET] Cached match result for doc={document_hash[:12]}...")

        return result

    @staticmethod
    def _empty_job_match() -> EnrichedJobMatchResult:
        return EnrichedJobMatchResult(
            job_id="general",
            job_title="General Role",
            department="General",
            vacancy_id=None,
            job_profile_id=None,
            company_id=None,
            department_id=None,
            department_name="General",
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
    def _empty_analysis(cv_text: str = "") -> EnrichedCandidateAnalysis:
        cand_profile = (
            ScoringEngine.extract_candidate_domain_profile(cv_text=cv_text) if cv_text else {}
        )
        rec_dept = cand_profile.get("recommended_department", "General")
        prof_domain = cand_profile.get("professional_domain", "General Operations")
        strengths = cand_profile.get("strengths", ["General technical background"])
        roles = cand_profile.get("suitable_job_roles", ["Operations Associate"])
        best_match = MatchService._empty_job_match()

        return EnrichedCandidateAnalysis(
            primary_department=rec_dept,
            recommended_department=rec_dept,
            professional_domain=prof_domain,
            strengths=strengths,
            suitable_job_roles=roles,
            has_genuine_match=False,
            active_vacancy_summary="No suitable active vacancy found.",
            ai_career_summary=(
                f"Candidate Profile Analysis:\n"
                f"• Recommended Department: {rec_dept}\n"
                f"• Professional Domain: {prof_domain}\n"
                f"• Key Strengths: {'; '.join(strengths)}\n"
                f"• Suitable Job Roles: {', '.join(roles)}"
            ),
            best_match=best_match,
            suitable_openings=[],
        )

    @staticmethod
    async def analyze_from_result_file(result_json_path: str | Path) -> dict[str, Any]:
        data = ResultRepository.read_result(result_json_path)

        cv_text = data.get("markdown")
        if not cv_text:
            raise ValueError("No markdown text found in the result file.")

        cv_hash = data.get("cv_hash", "")
        cand_id = data.get("candidate_id", "")
        enriched_analysis = await MatchService.analyze_single_cv(
            cv_text,
            document_hash=cv_hash,
            candidate_id=cand_id,
        )

        # Merge back into data
        data["enriched_match_analysis"] = enriched_analysis.model_dump()

        # Save back or save as new
        path = Path(result_json_path)
        new_filename = f"{path.stem}_enriched.json"

        new_path = ResultRepository.save_result(new_filename, data)

        data["enriched_result_file_path"] = str(new_path)
        return data
