from __future__ import annotations
from typing import Any

from app.core.config import settings
from app.repositories.job import JobRepository
from app.repositories.result import ResultRepository
from app.schemas.scoring_config import ScoringConfig
from app.services.domain_embedding_service import DomainEmbeddingService


class RecommendationService:
    """
    Intelligent AI Recommendation Service for recruiters.
    Provides actionable insights across 7 intelligence domains:
    1. Best Vacancies for Candidate
    2. Similar Candidates for Vacancy
    3. Related Skills Recommendations
    4. Missing Qualifications & Skill Gaps
    5. Recommended Certifications
    6. Career Transition Opportunities
    7. Internal Talent Pools
    Embeddings are used strictly for retrieval and semantic expansion while preserving deterministic validation & scoring.
    """

    # (Hardcoded DOMAIN_CERTIFICATIONS and _FALLBACK_CERTIFICATIONS have been removed.
    # Certifications and limits are now dynamically derived via JobRepository and app.core.config.settings)

    @staticmethod
    def _is_strong_match(match: dict[str, Any], threshold: float) -> bool:
        score = float(match.get("score") or match.get("overall_score") or 0.0)
        classification = str(match.get("classification") or "").upper()
        failures = match.get("mandatory_failures") or match.get("mandatory_fails") or []
        has_domain_rejection = any(
            isinstance(failure, dict) and failure.get("requirement_id") == "req_domain_mismatch"
            for failure in failures
        )
        is_domain_rejected = match.get("domain_mismatch_capped") or match.get("is_cross_domain")
        is_high_class = classification in {"HIGH", "STRONG", "DB_MATCH", "HIGHLY_RECOMMENDED"}
        return score >= threshold and is_high_class and not is_domain_rejected and not has_domain_rejection

    @classmethod
    def get_candidate_recommendations(cls, candidate_id: str) -> dict[str, Any]:
        cid = candidate_id.strip()
        result_filename = f"{cid}.json" if not cid.endswith(".json") else cid
        cv_key = result_filename.removesuffix(".json")

        r = ResultRepository.resolve_result(cid)
        if not r:
            r = ResultRepository.read_result_by_filename(result_filename)

        if not r or not isinstance(r, dict) or r.get("status") == "processing":
            is_proc = isinstance(r, dict) and r.get("status") == "processing"
            status_msg = "Analysis in progress..." if is_proc else "N/A"
            return {
                "candidate_id": cv_key,
                "full_name": cv_key,
                "primary_department": "",
                "industry_role": None,
                "strengths": [],
                "overall_match_confidence": 0.0,
                "actionable_suggestions": [],
                "best_vacancies": [],
                "related_skills": [],
                "missing_qualifications": [],
                "recommended_certifications": [],
                "career_transitions": [],
                "talent_pools": [],
                "hiring_recommendation": "PROCESSING" if is_proc else "NO_STRONG_MATCH",
                "role_department_fit": status_msg,
                "experience_assessment": status_msg,
                "interview_focus_areas": [],
                "risk_flags": [],
                "technical_vs_functional_fit": status_msg,
                "next_steps_for_interviewer": [],
            }

        raw_match = r.get("match_analysis")
        match_analysis = raw_match if isinstance(raw_match, dict) else {}
        scoring_config = ScoringConfig.load()
        min_threshold = scoring_config.match_high_threshold
        suitable_openings = match_analysis.get("suitable_openings") or []
        eligible_openings = [
            opening
            for opening in suitable_openings
            if isinstance(opening, dict) and cls._is_strong_match(opening, min_threshold)
        ]
        stored_best_match = match_analysis.get("best_match") or {}
        if not eligible_openings and isinstance(stored_best_match, dict) and cls._is_strong_match(stored_best_match, min_threshold):
            eligible_openings = [stored_best_match]
        best_match = eligible_openings[0] if eligible_openings else {}

        resume_json = r.get("resume_json") or {}
        contact_info = resume_json.get("contact_info") or {}
        extracted_name = contact_info.get("name") or contact_info.get("full_name") or r.get("full_name") or r.get("candidate_name") or cv_key
        all_jobs = JobRepository.get_all_jobs()
        classification_data = match_analysis.get("classification") or {}
        industry_dept = None
        industry_domain = None
        if isinstance(classification_data, dict):
            industry_dept = classification_data.get("industry_department") or classification_data.get("db_department_name")
            industry_domain = classification_data.get("industry_domain")

        if eligible_openings and best_match:
            raw_dept = best_match.get("department") or best_match.get("department_name") or match_analysis.get("recommended_department") or match_analysis.get("primary_department") or industry_dept or ""
        else:
            raw_dept = ""
        primary_dept = str(raw_dept).title() if raw_dept else ""
        prof_domain = match_analysis.get("professional_domain") or industry_domain or ""

        # Secondary fallback: derive dept/domain from suitable_openings if primary chain is empty
        if not primary_dept.strip() and eligible_openings:
            for eo in eligible_openings:
                fallback_dept = eo.get("department") or eo.get("department_name") or ""
                if fallback_dept:
                    primary_dept = str(fallback_dept).title()
                    break
        if not prof_domain.strip() and primary_dept:
            prof_domain = primary_dept

        # 1. Extract candidate skills (structured skills + fallback to work experience extraction)
        raw_cand_skills = resume_json.get("skills") or best_match.get("matched_skills") or []
        if isinstance(raw_cand_skills, list):
            candidate_skills = [s for s in raw_cand_skills if isinstance(s, str) and s.strip()]
        elif isinstance(raw_cand_skills, dict):
            candidate_skills = []
            if isinstance(raw_cand_skills.get("all_skills"), list):
                candidate_skills.extend(s for s in raw_cand_skills["all_skills"] if isinstance(s, str) and s.strip())
            for sub in raw_cand_skills.values():
                if isinstance(sub, list):
                    candidate_skills.extend(s for s in sub if isinstance(s, str) and s.strip() and s not in candidate_skills)
        else:
            candidate_skills = []

        # When structured skills are empty, extract key terms from work experience
        if not candidate_skills:
            candidate_skills = cls._extract_skills_from_work_experience(resume_json, r.get("text") or r.get("markdown") or "", all_jobs)

        cand_skills_lower_set = {s.lower() for s in candidate_skills}

        # Extract candidate existing certifications
        raw_certs = resume_json.get("certifications") or resume_json.get("licenses_certifications") or []
        existing_certs = []
        if isinstance(raw_certs, list):
            for c in raw_certs:
                if isinstance(c, str) and c.strip():
                    existing_certs.append(c.strip())
                elif isinstance(c, dict) and c.get("name"):
                    existing_certs.append(str(c.get("name")).strip())
        existing_certs_lower = {c.lower() for c in existing_certs}

        # Extract candidate strengths
        strengths = match_analysis.get("strengths") or []
        if not strengths:
            if candidate_skills:
                strengths.append(f"Core Technical Skills: {', '.join(candidate_skills[:4])}")
            if existing_certs:
                strengths.append(f"Documented Certifications: {', '.join(existing_certs[:2])}")
            exp_yrs = (r.get("quality_metrics") or {}).get("experience_years") or 0.0
            if exp_yrs > 0:
                strengths.append(f"Professional Experience: {exp_yrs} years in {prof_domain}")

        best_vacancies = []
        for vac in eligible_openings[: settings.MAX_RECOMMENDED_VACANCIES]:
            if isinstance(vac, dict):
                best_vacancies.append(
                    {
                        "vacancy_id": vac.get("vacancy_id") or vac.get("id") or vac.get("job_id"),
                        "job_title": vac.get("job_title"),
                        "department": vac.get("department") or vac.get("department_name"),
                        "score": float(vac.get("score") or vac.get("overall_score") or 0.0),
                        "classification": vac.get("classification"),
                        "recommendation": vac.get("recommendation"),
                        "reason": vac.get("ranking_reason") or vac.get("reason"),
                    }
                )

        overall_confidence = best_vacancies[0]["score"] if best_vacancies else 0.0

        # 3. Semantically Related Skills Recommendations (via DomainEmbeddingService with no live Ollama generation)
        related_skills_set = set()
        for skill in candidate_skills[:5]:
            eqs = DomainEmbeddingService.find_semantic_equivalents(term=skill, category="skills", limit=3, allow_live_generation=False)
            for eq in eqs:
                eq_term = eq["term"].title()
                if eq_term.lower() not in cand_skills_lower_set:
                    related_skills_set.add(eq_term)

        related_skills = list(related_skills_set)[: settings.MAX_RELATED_SKILLS]

        # 4. Missing Qualifications & Skill Gap Insights (Aggregated across suitable openings)
        missing_quals = []
        seen_gaps = set()

        openings_to_check = eligible_openings
        for vac in openings_to_check[: settings.MAX_MISSING_QUALS]:
            if not isinstance(vac, dict):
                continue
            job_title = vac.get("job_title") or "Target Vacancy"
            vac_score = vac.get("score") or vac.get("overall_score") or 0.0

            missing_skills = vac.get("missing_skills") or []
            missing_criteria = vac.get("missing_criteria") or []
            mandatory_fails = vac.get("mandatory_fails") or []

            for ms in missing_skills[:4]:
                if isinstance(ms, str) and ms.strip() and ms.lower() not in seen_gaps:
                    seen_gaps.add(ms.lower())
                    missing_quals.append(
                        {
                            "requirement": f"Missing Skill: {ms.title()}",
                            "impact": f"Critical requirement to increase match score on {job_title} ({vac_score}% match)",
                            "type": "Skill",
                            "actionable_suggestion": f"Acquire practical experience with {ms.title()} to qualify for {job_title}.",
                        }
                    )

            for mf in mandatory_fails[:2]:
                req_name = mf.get("requirement") if isinstance(mf, dict) else str(mf)
                if req_name and req_name.lower() not in seen_gaps:
                    seen_gaps.add(req_name.lower())
                    missing_quals.append(
                        {
                            "requirement": f"Mandatory Constraint: {req_name}",
                            "impact": f"High severity penalty on suitability for {job_title}",
                            "type": "Mandatory Requirement",
                            "actionable_suggestion": f"Verify eligibility regarding {req_name}.",
                        }
                    )

            for mc in missing_criteria[:2]:
                if isinstance(mc, str) and mc.strip() and mc.lower() not in seen_gaps:
                    seen_gaps.add(mc.lower())
                    missing_quals.append(
                        {
                            "requirement": mc,
                            "impact": f"Improves candidate score alignment for {job_title}",
                            "type": "Criterion",
                            "actionable_suggestion": f"Address {mc} to strengthen profile alignment.",
                        }
                    )

        # 5. Dynamic Recommended Certifications (Domain-aware + evidence-based from active vacancies)
        recommended_certs = []
        domain_jobs = [
            j
            for j in all_jobs
            if isinstance(j, dict)
            and (
                primary_dept.lower() in str(j.get("department") or j.get("department_name") or "").lower() or str(j.get("department") or j.get("department_name") or "").lower() in primary_dept.lower()
            )
        ]
        if not domain_jobs:
            domain_jobs = [j for j in all_jobs if isinstance(j, dict)]

        # Resolve domain-aware certification keywords dynamically from domain jobs
        import re

        cert_pattern = re.compile(
            r"\b([A-Z][a-zA-Z0-9-]*\s+(?:Certification|Certified|License))\b",
            re.IGNORECASE,
        )
        found_job_certs = set()

        for j in domain_jobs:
            req_text = " ".join(
                [
                    str(j.get("QualificationReq") or ""),
                    str(j.get("JobDescription") or ""),
                    str(j.get("MandatorySkillsReq") or ""),
                    str(j.get("PreferredKeywords") or ""),
                    str(j.get("title") or j.get("JobTitle") or ""),
                ]
            )
            matches = cert_pattern.findall(req_text)
            for m in matches:
                kw = m.strip().title()
                if not any(kw.lower() in ec.lower() for ec in existing_certs_lower):
                    found_job_certs.add(kw)

        recommended_certs = sorted(found_job_certs)[: settings.MAX_RECOMMENDED_CERTS]

        # 6. Hiring-focused Metrics
        suitable_roles = match_analysis.get("suitable_job_roles") or []
        industry_role = suitable_roles[0] if suitable_roles else None
        if not best_vacancies:
            hiring_rec = "NO_STRONG_MATCH"
            if primary_dept or prof_domain or suitable_roles:
                dept_desc = primary_dept if primary_dept else "relevant industry"
                domain_desc = f"{prof_domain} experience" if prof_domain else "technical capabilities"
                roles_desc = f" ({', '.join(suitable_roles[:2])})" if suitable_roles else ""
                role_dept_fit = (
                    f"Candidate aligns with {dept_desc} roles{roles_desc} based on {domain_desc}. "
                    "No active vacancy match currently open."
                )
            else:
                role_dept_fit = "N/A"
        else:
            if overall_confidence >= 85:
                hiring_rec = "Highly Recommended"
            elif overall_confidence >= min_threshold:
                hiring_rec = "Recommended"
            else:
                hiring_rec = "Needs Further Review"

            role_dept_fit = (
                f"Strong alignment for {primary_dept} roles based on {prof_domain} experience."
            )

        # Generate Interview Focus Areas
        interview_focus_areas = []
        if missing_quals:
            interview_focus_areas.append(f"Probe deeply on gaps: {missing_quals[0].get('requirement', 'Technical requirements')}")
        if candidate_skills:
            interview_focus_areas.append(f"Validate claimed expertise in {candidate_skills[0].title()} and {candidate_skills[1].title() if len(candidate_skills) > 1 else 'core domain tools'}.")
        interview_focus_areas.append(f"Assess cultural and departmental fit for {primary_dept}.")

        # Generate Risk Flags
        risk_flags = []
        for qual in missing_quals:
            if "Mandatory" in qual.get("requirement", "") or "Critical" in qual.get("impact", ""):
                risk_flags.append(qual.get("requirement"))

        from app.services.experience_calculator import ExperienceCalculator

        norm_resume = r.get("normalized_resume") or {}

        canonical_exp = ExperienceCalculator.calculate_canonical_experience(
            resume_json, r.get("text") or r.get("markdown") or "", candidate_id=cv_key
        )

        exp_years = float(canonical_exp["experience_years"])
        exp_tier = canonical_exp["seniority"]

        if exp_years < 1.0 and not resume_json.get("work_experience") and not norm_resume.get("employment"):
            risk_flags.append("Limited professional experience verified in profile.")

        experience_assessment = canonical_exp["experience_assessment"]

        # Technical vs Functional Fit
        tech_vs_func = "Balanced technical and functional foundation."
        if candidate_skills and len(candidate_skills) > 5:
            tech_vs_func = "Heavy technical lean; recommend assessing functional communication skills."

        # 7. Internal Talent Pools (Evidence-based classification)
        talent_pools = [f"{primary_dept} - {exp_tier} Talent Pool"] if best_vacancies and primary_dept else []
        if talent_pools and candidate_skills:
            talent_pools.append(f"{candidate_skills[0].title()} Specialists Pool")

        # 8. Career Transition Opportunities
        career_transitions = []
        if best_vacancies:
            target_jobs = domain_jobs if len(domain_jobs) > 1 else (all_jobs or domain_jobs)
            best_title = (best_match.get("job_title") or "").lower()
            for vac in target_jobs:
                if not isinstance(vac, dict):
                    continue
                vac_title = vac.get("title") or vac.get("JobTitle") or "Target Role"
                vac_dept = vac.get("department") or vac.get("department_name") or primary_dept
                if vac_title.lower() != best_title and not any(ct["target_role"].lower() == vac_title.lower() for ct in career_transitions):
                    vac_req_skills = vac.get("required_skills") or vac.get("SkillsReq") or []
                    if isinstance(vac_req_skills, str):
                        vac_req_skills = [s.strip() for s in vac_req_skills.split(",") if s.strip()]
                    skill_bridge = vac_req_skills[:2] if vac_req_skills else ["Domain Knowledge"]

                    career_transitions.append(
                        {
                            "target_role": vac_title,
                            "target_department": vac_dept,
                            "feasibility_score": round(max(40.0, overall_confidence - 10.0), 1),
                            "transition_path": f"Transition from {prof_domain} to {vac_title} by building {vac_dept} experience.",
                            "skill_bridge": skill_bridge,
                        }
                    )
                if len(career_transitions) >= 3:
                    break

        # 9. Actionable Next Steps & Suggestions
        next_steps = []
        if hiring_rec in ("Highly Recommended", "Recommended", "HIRE"):
            next_steps.append("Fast-track to technical screening.")
        elif hiring_rec in ("Potential Fit", "CONSIDER"):
            next_steps.append("Schedule introductory call to clarify experience gaps.")
        else:
            next_steps.append("Review the separate industry-role evidence; do not assign an internal department or talent pool.")

        for qual in missing_quals[:1]:
            if qual.get("actionable_suggestion"):
                next_steps.append(qual["actionable_suggestion"])

        return {
            "candidate_id": cv_key,
            "full_name": extracted_name,
            "primary_department": primary_dept,
            "industry_role": industry_role,
            "strengths": strengths,
            "overall_match_confidence": overall_confidence,
            "best_vacancies": best_vacancies,
            "related_skills": related_skills,
            "missing_qualifications": missing_quals,
            "recommended_certifications": recommended_certs,
            "career_transitions": career_transitions,
            "talent_pools": talent_pools,
            "hiring_recommendation": hiring_rec,
            "role_department_fit": role_dept_fit,
            "interview_focus_areas": interview_focus_areas,
            "risk_flags": risk_flags,
            "experience_assessment": experience_assessment,
            "experience_gap_analysis": canonical_exp.get("gap_analysis"),
            "technical_vs_functional_fit": tech_vs_func,
            "next_steps_for_interviewer": next_steps,
            "actionable_suggestions": next_steps,
        }

    @classmethod
    def _extract_skills_from_work_experience(
        cls,
        resume_json: dict[str, Any] | None,
        cv_text: str,
        all_jobs: list[dict[str, Any]],
    ) -> list[str]:
        """
        Extracts meaningful skill/technology terms from work experience
        responsibilities and CV text when structured skills are empty.
        Uses dynamic required skills from active jobs as the taxonomy.
        """
        # Dynamically build skill taxonomy from all active jobs
        _SKILL_TERMS = set()
        for j in all_jobs:
            if not isinstance(j, dict):
                continue
            raw_j_skills = j.get("required_skills") or j.get("SkillsReq") or []
            if isinstance(raw_j_skills, str):
                for s in raw_j_skills.split(","):
                    if s.strip():
                        _SKILL_TERMS.add(s.strip().lower())
            elif isinstance(raw_j_skills, list):
                for s in raw_j_skills:
                    if str(s).strip():
                        _SKILL_TERMS.add(str(s).strip().lower())

        found_skills: list[str] = []
        seen: set[str] = set()

        # Build search text from work experience + CV text
        search_parts: list[str] = []
        if resume_json:
            for exp in resume_json.get("work_experience") or []:
                if not isinstance(exp, dict):
                    continue
                for resp in exp.get("responsibilities") or []:
                    if isinstance(resp, str):
                        search_parts.append(resp)
                if exp.get("description"):
                    search_parts.append(str(exp["description"]))
        if cv_text:
            search_parts.append(cv_text)

        search_text = " ".join(search_parts).lower()
        if not search_text.strip():
            return []

        for term in _SKILL_TERMS:
            if term in search_text and term not in seen:
                found_skills.append(term.title())
                seen.add(term)
            if len(found_skills) >= 10:
                break

        return found_skills

    @classmethod
    def get_vacancy_recommendations(cls, vacancy_id: str) -> dict[str, Any]:
        vid_str = str(vacancy_id).strip()
        all_jobs = JobRepository.get_all_jobs()
        target_job = None
        for j in all_jobs:
            if str(j.get("vacancy_id")) == vid_str or str(j.get("id")) == vid_str:
                target_job = j
                break

        if not target_job:
            return {
                "vacancy_id": vid_str,
                "top_candidate_matches": [],
                "similar_candidates": [],
                "skill_gap_insights": [],
                "talent_pools": [],
            }

        vac_title = target_job.get("title", "Vacancy")
        req_skills = [s.lower() for s in target_job.get("required_skills", []) if isinstance(s, str)]

        # Top Candidate Matches
        min_threshold = ScoringConfig.load().match_high_threshold
        all_results = ResultRepository.list_all_results()
        scored_candidates = []
        for r in all_results:
            if not r or not isinstance(r, dict):
                continue
            raw_match = r.get("match_analysis")
            match_analysis = raw_match if isinstance(raw_match, dict) else {}
            suitable = match_analysis.get("suitable_openings") or []
            for s in suitable:
                if isinstance(s, dict) and cls._is_strong_match(s, min_threshold) and (str(s.get("vacancy_id")) == vid_str or str(s.get("id")) == vid_str):
                    score = float(s.get("score") or s.get("overall_score") or 0.0)
                    scored_candidates.append((score, r, s))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        top_candidate_matches = []
        for score, r, s in scored_candidates[:5]:
            cv_key = str(r.get("id") or r.get("filename") or "")
            contact_info = (r.get("resume_json") or {}).get("contact_info") or {}
            cname = contact_info.get("name") or contact_info.get("full_name") or cv_key

            top_candidate_matches.append(
                {
                    "candidate_id": cv_key,
                    "full_name": cname,
                    "match_score": score,
                    "classification": s.get("classification"),
                    "recommendation": s.get("recommendation"),
                }
            )

        # Skill Gap Insights
        skill_gap_insights = []
        for req in req_skills[:3]:
            skill_gap_insights.append(
                {
                    "skill": req.title(),
                    "market_rarity": "Medium Demand",
                    "recommendation": f"Include {req.title()} in interview technical evaluation.",
                }
            )

        return {
            "vacancy_id": vid_str,
            "job_title": vac_title,
            "department": target_job.get("department_name") or target_job.get("department") or "Unspecified",
            "top_candidate_matches": top_candidate_matches,
            "similar_candidates": top_candidate_matches[:3],
            "skill_gap_insights": skill_gap_insights,
            "talent_pools": [f"{target_job.get('department_name') or target_job.get('department') or 'Unspecified'} Pool"],
        }

    @classmethod
    def get_internal_talent_pools(cls) -> dict[str, Any]:
        all_results = ResultRepository.list_all_results()
        min_threshold = ScoringConfig.load().match_high_threshold

        pools: dict[str, list[dict[str, Any]]] = {}

        for r in all_results:
            if not r or not isinstance(r, dict):
                continue
            cv_key = str(r.get("id") or r.get("filename") or "")
            match_analysis = r.get("match_analysis") or {}
            suitable = match_analysis.get("suitable_openings") or []
            strong_matches = [
                match
                for match in suitable
                if isinstance(match, dict) and cls._is_strong_match(match, min_threshold)
            ]
            if not strong_matches:
                continue
            dept = str(strong_matches[0].get("department") or strong_matches[0].get("department_name") or "").title()
            if not dept:
                continue
            pool_name = f"{dept} Talent Pool"

            contact_info = (r.get("resume_json") or {}).get("contact_info") or {}
            cname = contact_info.get("name") or contact_info.get("full_name") or cv_key

            if pool_name not in pools:
                pools[pool_name] = []

            raw_skills = (r.get("resume_json") or {}).get("skills")
            if isinstance(raw_skills, list):
                cand_skills = [s for s in raw_skills if isinstance(s, str)]
            elif isinstance(raw_skills, dict):
                cand_skills = [s for sub in raw_skills.values() if isinstance(sub, list) for s in sub if isinstance(s, str)]
            else:
                cand_skills = []

            pools[pool_name].append(
                {
                    "candidate_id": cv_key,
                    "full_name": cname,
                    "skills": cand_skills[:3],
                    "experience_years": (r.get("quality_metrics") or {}).get("experience_years"),
                }
            )

        summary = []
        for name, cands in pools.items():
            summary.append(
                {
                    "pool_name": name,
                    "candidate_count": len(cands),
                    "sample_candidates": cands[:3],
                }
            )

        return {
            "total_pools": len(summary),
            "talent_pools": summary,
        }
