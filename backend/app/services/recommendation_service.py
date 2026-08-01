from typing import Any

from app.core.config import settings
from app.repositories.job import JobRepository
from app.repositories.result import ResultRepository
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

    @classmethod
    def get_candidate_recommendations(cls, candidate_id: str) -> dict[str, Any]:
        cid = candidate_id.strip()
        result_filename = f"{cid}.json" if not cid.endswith(".json") else cid
        cv_key = result_filename.removesuffix(".json")

        r = ResultRepository.read_result_by_filename(result_filename)
        if not r:
            matches = ResultRepository.find_results_by_scan_id(cv_key)
            if matches:
                r = ResultRepository.read_result(matches[0])

        if not r or not isinstance(r, dict) or r.get("status") == "processing":
            return {
                "candidate_id": cv_key,
                "full_name": cv_key,
                "primary_department": "Unspecified",
                "strengths": [],
                "overall_match_confidence": 0.0,
                "actionable_suggestions": [],
                "best_vacancies": [],
                "related_skills": [],
                "missing_qualifications": [],
                "recommended_certifications": [],
                "career_transitions": [],
                "talent_pools": [],
            }

        raw_match = r.get("match_analysis")
        match_analysis = raw_match if isinstance(raw_match, dict) else {}
        best_match = match_analysis.get("best_match") or {}

        resume_json = r.get("resume_json") or {}
        contact_info = resume_json.get("contact_info") or {}
        extracted_name = (
            contact_info.get("name")
            or contact_info.get("full_name")
            or r.get("full_name")
            or r.get("candidate_name")
            or cv_key
        )
        all_jobs = JobRepository.get_all_jobs()
        # Dynamically derive fallback department from the most common department among active jobs
        fallback_dept = "Unspecified"
        if all_jobs:
            dept_counts = {}
            for j in all_jobs:
                d = j.get("department_name") or j.get("department")
                if d and isinstance(d, str):
                    dept_counts[d] = dept_counts.get(d, 0) + 1
            if dept_counts:
                fallback_dept = max(dept_counts, key=dept_counts.get)

        primary_dept = (
            match_analysis.get("primary_department")
            or match_analysis.get("recommended_department")
            or best_match.get("department")
            or fallback_dept
        ).title()
        
        prof_domain = (
            match_analysis.get("professional_domain")
            or fallback_dept
        )

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

        # 2. Best Vacancies for Candidate (Deterministic Scoring Engine authority)
        suitable_openings = match_analysis.get("suitable_openings") or []
        best_vacancies = []
        for vac in suitable_openings[:settings.MAX_RECOMMENDED_VACANCIES]:
            if isinstance(vac, dict):
                best_vacancies.append({
                    "vacancy_id": vac.get("vacancy_id") or vac.get("id") or vac.get("job_id"),
                    "job_title": vac.get("job_title"),
                    "department": vac.get("department") or vac.get("department_name"),
                    "score": vac.get("score") or vac.get("overall_score") or 0.0,
                    "classification": vac.get("classification"),
                    "recommendation": vac.get("recommendation"),
                    "reason": vac.get("ranking_reason") or vac.get("reason"),
                })

        overall_confidence = float(best_match.get("overall_score") or best_match.get("score") or (best_vacancies[0]["score"] if best_vacancies else 0.0))

        # 3. Semantically Related Skills Recommendations (via DomainEmbeddingService with no live Ollama generation)
        related_skills_set = set()
        for skill in candidate_skills[:5]:
            eqs = DomainEmbeddingService.find_semantic_equivalents(
                term=skill, category="skills", limit=3, allow_live_generation=False
            )
            for eq in eqs:
                eq_term = eq["term"].title()
                if eq_term.lower() not in cand_skills_lower_set:
                    related_skills_set.add(eq_term)

        related_skills = list(related_skills_set)[:settings.MAX_RELATED_SKILLS]

        # 4. Missing Qualifications & Skill Gap Insights (Aggregated across suitable openings)
        missing_quals = []
        seen_gaps = set()

        openings_to_check = suitable_openings if suitable_openings else ([best_match] if best_match else [])
        for vac in openings_to_check[:settings.MAX_MISSING_QUALS]:
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
                    missing_quals.append({
                        "requirement": f"Missing Skill: {ms.title()}",
                        "impact": f"Critical requirement to increase match score on {job_title} ({vac_score}% match)",
                        "type": "Skill",
                        "actionable_suggestion": f"Acquire practical experience with {ms.title()} to qualify for {job_title}.",
                    })

            for mf in mandatory_fails[:2]:
                req_name = mf.get("requirement") if isinstance(mf, dict) else str(mf)
                if req_name and req_name.lower() not in seen_gaps:
                    seen_gaps.add(req_name.lower())
                    missing_quals.append({
                        "requirement": f"Mandatory Constraint: {req_name}",
                        "impact": f"High severity penalty on suitability for {job_title}",
                        "type": "Mandatory Requirement",
                        "actionable_suggestion": f"Verify eligibility regarding {req_name}.",
                    })

            for mc in missing_criteria[:2]:
                if isinstance(mc, str) and mc.strip() and mc.lower() not in seen_gaps:
                    seen_gaps.add(mc.lower())
                    missing_quals.append({
                        "requirement": mc,
                        "impact": f"Improves candidate score alignment for {job_title}",
                        "type": "Criterion",
                        "actionable_suggestion": f"Address {mc} to strengthen profile alignment.",
                    })

        # 5. Dynamic Recommended Certifications (Domain-aware + evidence-based from active vacancies)
        recommended_certs = []
        domain_jobs = [
            j for j in all_jobs
            if isinstance(j, dict) and (
                primary_dept.lower() in str(j.get("department") or j.get("department_name") or "").lower()
                or str(j.get("department") or j.get("department_name") or "").lower() in primary_dept.lower()
            )
        ]
        if not domain_jobs:
            domain_jobs = [j for j in all_jobs if isinstance(j, dict)]

        # Resolve domain-aware certification keywords dynamically from domain jobs
        import re
        cert_pattern = re.compile(r'\b([A-Z][a-zA-Z0-9-]*\s+(?:Certification|Certified|License))\b', re.IGNORECASE)
        found_job_certs = set()

        for j in domain_jobs:
            req_text = " ".join([
                str(j.get("QualificationReq") or ""),
                str(j.get("JobDescription") or ""),
                str(j.get("MandatorySkillsReq") or ""),
                str(j.get("PreferredKeywords") or ""),
                str(j.get("title") or j.get("JobTitle") or ""),
            ])
            matches = cert_pattern.findall(req_text)
            for m in matches:
                kw = m.strip().title()
                if not any(kw.lower() in ec.lower() for ec in existing_certs_lower):
                    found_job_certs.add(kw)

        recommended_certs = sorted(found_job_certs)[:settings.MAX_RECOMMENDED_CERTS]

        # 6. Hiring-focused Metrics
        if overall_confidence >= 85:
            hiring_rec = "Highly Recommended"
        elif overall_confidence >= 70:
            hiring_rec = "Recommended"
        elif overall_confidence >= 55:
            hiring_rec = "Potential Fit"
        else:
            hiring_rec = "Needs Further Review"

        role_dept_fit = f"Strong alignment for {primary_dept} roles based on {prof_domain} experience." if overall_confidence >= 70 else f"Marginal fit for {primary_dept}; requires validation of {prof_domain} transferability."

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
        
        exp_years = (r.get("quality_metrics") or {}).get("experience_years") or 0.0
        exp_tier = "Junior"
        for tier, threshold in sorted(settings.EXPERIENCE_BANDS.items(), key=lambda x: x[1], reverse=True):
            if exp_years >= threshold:
                exp_tier = tier
                break

        if exp_years < 1.0:
            risk_flags.append("Limited professional experience verified in profile.")

        # Experience & Seniority Assessment
        experience_assessment = f"Assessed as {exp_tier} level with approximately {exp_years} years of relevant domain experience."

        # Technical vs Functional Fit
        tech_vs_func = "Balanced technical and functional foundation."
        if candidate_skills and len(candidate_skills) > 5:
            tech_vs_func = "Heavy technical lean; recommend assessing functional communication skills."

        # 7. Internal Talent Pools (Evidence-based classification)
        talent_pools = [
            f"{primary_dept} - {exp_tier} Talent Pool",
        ]
        if candidate_skills:
            talent_pools.append(f"{candidate_skills[0].title()} Specialists Pool")

        # 8. Career Transition Opportunities
        career_transitions = []
        target_jobs = domain_jobs if len(domain_jobs) > 1 else (all_jobs or domain_jobs)
        best_title = (best_match.get("job_title") or "").lower()
        for vac in target_jobs:
            if not isinstance(vac, dict):
                continue
            vac_title = vac.get("title") or vac.get("JobTitle") or "Target Role"
            vac_dept = vac.get("department") or vac.get("department_name") or primary_dept
            if vac_title.lower() != best_title and not any(ct["target_role"].lower() == vac_title.lower() for ct in career_transitions):
                career_transitions.append({
                    "target_role": vac_title,
                    "target_department": vac_dept,
                    "feasibility_score": round(max(40.0, overall_confidence - 10.0), 1),
                    "transition_path": f"Transition from {prof_domain} to {vac_title} by building {vac_dept} experience.",
                    "skill_bridge": candidate_skills[:2] if candidate_skills else ["Domain Knowledge"],
                })
            if len(career_transitions) >= 3:
                break

        # 9. Actionable Next Steps & Suggestions
        next_steps = []
        if hiring_rec in ("Highly Recommended", "Recommended", "HIRE"):
            next_steps.append("Fast-track to technical screening.")
        elif hiring_rec in ("Potential Fit", "CONSIDER"):
            next_steps.append("Schedule introductory call to clarify experience gaps.")
        else:
            next_steps.append("Keep in talent pool for future junior roles.")
        
        for qual in missing_quals[:1]:
            if qual.get("actionable_suggestion"):
                next_steps.append(qual["actionable_suggestion"])

        return {
            "candidate_id": cv_key,
            "full_name": extracted_name,
            "primary_department": primary_dept,
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
        all_results = ResultRepository.list_all_results()
        scored_candidates = []
        for r in all_results:
            if not r or not isinstance(r, dict):
                continue
            raw_match = r.get("match_analysis")
            match_analysis = raw_match if isinstance(raw_match, dict) else {}
            suitable = match_analysis.get("suitable_openings") or []
            for s in suitable:
                if isinstance(s, dict) and (str(s.get("vacancy_id")) == vid_str or str(s.get("id")) == vid_str):
                    score = float(s.get("score") or s.get("overall_score") or 0.0)
                    scored_candidates.append((score, r, s))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        top_candidate_matches = []
        for score, r, s in scored_candidates[:5]:
            cv_key = str(r.get("id") or r.get("filename") or "")
            contact_info = (r.get("resume_json") or {}).get("contact_info") or {}
            cname = contact_info.get("name") or contact_info.get("full_name") or cv_key

            top_candidate_matches.append({
                "candidate_id": cv_key,
                "full_name": cname,
                "match_score": score,
                "classification": s.get("classification"),
                "recommendation": s.get("recommendation"),
            })

        # Skill Gap Insights
        skill_gap_insights = []
        for req in req_skills[:3]:
            skill_gap_insights.append({
                "skill": req.title(),
                "market_rarity": "Medium Demand",
                "recommendation": f"Include {req.title()} in interview technical evaluation.",
            })

        return {
            "vacancy_id": vid_str,
            "job_title": vac_title,
            "department": target_job.get("department_name") or target_job.get("department") or "Unspecified",
            "top_candidate_matches": top_candidate_matches,
            "similar_candidates": top_candidate_matches[:3],
            "skill_gap_insights": skill_gap_insights,
            "talent_pools": [f"{target_job.get('department_name') or target_job.get('department') or 'General'} Pool"],
        }

    @classmethod
    def get_internal_talent_pools(cls) -> dict[str, Any]:
        all_results = ResultRepository.list_all_results()

        pools: dict[str, list[dict[str, Any]]] = {}

        for r in all_results:
            if not r or not isinstance(r, dict):
                continue
            cv_key = str(r.get("id") or r.get("filename") or "")
            dept = str(
                (r.get("match_analysis") or {}).get("primary_department") or "Unspecified"
            ).title()
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

            pools[pool_name].append({
                "candidate_id": cv_key,
                "full_name": cname,
                "skills": cand_skills[:3],
                "experience_years": (r.get("quality_metrics") or {}).get("experience_years"),
            })

        summary = []
        for name, cands in pools.items():
            summary.append({
                "pool_name": name,
                "candidate_count": len(cands),
                "sample_candidates": cands[:3],
            })

        return {
            "total_pools": len(summary),
            "talent_pools": summary,
        }
