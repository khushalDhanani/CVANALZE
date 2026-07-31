from typing import Any

from app.core.logging import logger
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

    @classmethod
    def get_candidate_recommendations(cls, candidate_id: str) -> dict[str, Any]:
        cid = candidate_id.strip()
        result_filename = f"{cid}.json" if not cid.endswith(".json") else cid
        cv_key = result_filename[:-5] if result_filename.endswith(".json") else result_filename

        r = ResultRepository.read_result_by_filename(result_filename)
        if not r:
            matches = ResultRepository.find_results_by_scan_id(cv_key)
            if matches:
                r = ResultRepository.read_result(matches[0])

        if not r or not isinstance(r, dict) or r.get("status") == "processing":
            return {
                "candidate_id": cv_key,
                "full_name": cv_key,
                "primary_department": "General",
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
        primary_dept = (
            match_analysis.get("primary_department")
            or match_analysis.get("recommended_department")
            or best_match.get("department")
            or "Engineering"
        ).title()
        prof_domain = (
            match_analysis.get("professional_domain")
            or "General Operations"
        )

        # 1. Extract candidate skills
        raw_cand_skills = resume_json.get("skills") or best_match.get("matched_skills") or []
        if isinstance(raw_cand_skills, list):
            candidate_skills = [s for s in raw_cand_skills if isinstance(s, str) and s.strip()]
        elif isinstance(raw_cand_skills, dict):
            candidate_skills = [
                s for sub in raw_cand_skills.values()
                if isinstance(sub, list)
                for s in sub if isinstance(s, str) and s.strip()
            ]
        else:
            candidate_skills = []

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
        for vac in suitable_openings[:5]:
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

        # 3. Semantically Related Skills Recommendations (via DomainEmbeddingService)
        related_skills_set = set()
        for skill in candidate_skills[:5]:
            eqs = DomainEmbeddingService.find_semantic_equivalents(term=skill, category="skills", limit=3)
            for eq in eqs:
                eq_term = eq["term"].title()
                if eq_term.lower() not in cand_skills_lower_set:
                    related_skills_set.add(eq_term)

        related_skills = list(related_skills_set)[:8]

        # 4. Missing Qualifications & Skill Gap Insights (Aggregated across suitable openings)
        missing_quals = []
        seen_gaps = set()

        openings_to_check = suitable_openings if suitable_openings else ([best_match] if best_match else [])
        for vac in openings_to_check[:3]:
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

        # 5. Dynamic Recommended Certifications (Evidence-based from active JobRepository vacancies)
        recommended_certs = []
        all_jobs = JobRepository.get_all_jobs()
        domain_jobs = [
            j for j in all_jobs
            if isinstance(j, dict) and (
                primary_dept.lower() in str(j.get("department") or j.get("department_name") or "").lower()
                or str(j.get("department") or j.get("department_name") or "").lower() in primary_dept.lower()
            )
        ]
        if not domain_jobs:
            domain_jobs = [j for j in all_jobs if isinstance(j, dict)]

        cert_keywords = [
            "AWS Certified", "Kubernetes", "CKA", "SysOps", "Terraform", "CCNA",
            "PMP", "Scrum Master", "PSM", "CSPO", "ISTQB", "Selenium", "SHRM", "PHR",
            "Azure", "GCP", "Databricks", "CISSP", "CPA", "TOGAF"
        ]

        found_job_certs = set()
        for j in domain_jobs:
            req_text = " ".join([
                str(j.get("QualificationReq") or ""),
                str(j.get("JobDescription") or ""),
                str(j.get("MandatorySkillsReq") or ""),
                str(j.get("PreferredKeywords") or ""),
                str(j.get("title") or j.get("JobTitle") or ""),
            ])
            for kw in cert_keywords:
                if kw.lower() in req_text.lower():
                    if not any(kw.lower() in ec.lower() for ec in existing_certs_lower):
                        found_job_certs.add(kw)

        recommended_certs = [f"{c} Certification" if not c.lower().endswith("certification") else c for c in sorted(list(found_job_certs))[:4]]

        # 6. Dynamic Career Transition Opportunities (Calculated skill overlap against active jobs)
        career_transitions = []
        cand_role = (best_match.get("job_title") or prof_domain).lower()

        for j in all_jobs:
            if not isinstance(j, dict):
                continue
            job_title = j.get("title") or j.get("JobTitle") or j.get("vacancy_name")
            if not job_title or job_title.lower() in cand_role or cand_role in job_title.lower():
                continue

            raw_j_skills = j.get("required_skills") or j.get("SkillsReq") or []
            if isinstance(raw_j_skills, str):
                j_skills = [s.strip().lower() for s in raw_j_skills.split(",") if s.strip()]
            elif isinstance(raw_j_skills, list):
                j_skills = [str(s).strip().lower() for s in raw_j_skills if str(s).strip()]
            else:
                j_skills = []

            if not j_skills:
                continue

            matching_skills = [s for s in candidate_skills if s.lower() in j_skills or any(s.lower() in js for js in j_skills)]
            overlap_pct = (len(matching_skills) / len(j_skills)) * 100.0 if j_skills else 0.0

            if overlap_pct >= 40.0:
                feasibility_score = round(min(95.0, max(40.0, overlap_pct)), 1)
                transferable = [s.title() for s in matching_skills[:3]] if matching_skills else candidate_skills[:2]
                career_transitions.append({
                    "target_role": job_title,
                    "transferable_skills": transferable,
                    "feasibility_score": feasibility_score,
                    "growth_note": f"Demonstrates strong skill overlap ({len(matching_skills)} matching requirements) with core strengths in {', '.join(transferable[:2])}.",
                })

        career_transitions.sort(key=lambda x: x["feasibility_score"], reverse=True)

        # 7. Internal Talent Pools (Evidence-based classification)
        exp_years = (r.get("quality_metrics") or {}).get("experience_years") or 0.0
        exp_tier = "Senior" if exp_years >= 5.0 else ("Mid-Level" if exp_years >= 2.0 else "Junior")
        talent_pools = [
            f"{primary_dept} - {exp_tier} Talent Pool",
        ]
        if candidate_skills:
            talent_pools.append(f"{candidate_skills[0].title()} Specialists Pool")

        # 8. Actionable Suggestions
        actionable_suggestions = []
        for qual in missing_quals[:2]:
            if qual.get("actionable_suggestion"):
                actionable_suggestions.append(qual["actionable_suggestion"])
        if recommended_certs:
            actionable_suggestions.append(f"Consider obtaining {recommended_certs[0]} to enhance domain qualifications.")
        if career_transitions:
            actionable_suggestions.append(f"Potential transition path to {career_transitions[0]['target_role']} with {career_transitions[0]['feasibility_score']}% skill feasibility.")

        return {
            "candidate_id": cv_key,
            "full_name": extracted_name,
            "primary_department": primary_dept,
            "strengths": strengths,
            "overall_match_confidence": overall_confidence,
            "actionable_suggestions": actionable_suggestions,
            "best_vacancies": best_vacancies,
            "related_skills": related_skills,
            "missing_qualifications": missing_quals,
            "recommended_certifications": recommended_certs,
            "career_transitions": career_transitions[:3],
            "talent_pools": talent_pools,
        }

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
            "department": target_job.get("department_name") or target_job.get("department"),
            "top_candidate_matches": top_candidate_matches,
            "similar_candidates": top_candidate_matches[:3],
            "skill_gap_insights": skill_gap_insights,
            "talent_pools": [f"{target_job.get('department', 'Engineering')} Pool"],
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
                (r.get("match_analysis") or {}).get("primary_department") or "Engineering"
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
