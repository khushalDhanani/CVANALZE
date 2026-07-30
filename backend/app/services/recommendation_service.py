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

    DEPARTMENT_CERTIFICATION_MAP = {
        "engineering": ["AWS Certified Solutions Architect", "Certified Kubernetes Administrator (CKA)", "Professional Scrum Developer"],
        "infrastructure": ["AWS Certified SysOps Administrator", "HashiCorp Certified Terraform Associate", "CCNA"],
        "ui": ["Meta Front-End Developer Certificate", "UX Design Professional Certificate"],
        "analytics": ["Databricks Certified Data Engineer", "Google Data Analytics Certificate", "AWS Certified Data Analytics"],
        "quality": ["ISTQB Certified Tester", "Selenium Automation Tester Certification"],
        "product": ["PMI Agile Certified Practitioner (PMI-ACP)", "Certified Scrum Product Owner (CSPO)"],
        "hr": ["SHRM Certified Professional (SHRM-CP)", "PHR Certification"],
    }

    CAREER_TRANSITION_MAP = {
        "software engineer": ["DevOps Engineer", "Data Engineer", "Cloud Solutions Architect"],
        "python developer": ["Backend Architect", "Machine Learning Engineer", "Data Engineer"],
        "frontend developer": ["Full Stack Engineer", "UI/UX Engineer", "Mobile App Developer"],
        "qa engineer": ["SDET", "DevOps Engineer", "Backend Developer"],
    }

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

        if not r or not isinstance(r, dict):
            return {
                "candidate_id": cv_key,
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
        extracted_name = contact_info.get("name") or contact_info.get("full_name") or cv_key
        primary_dept = (match_analysis.get("primary_department") or best_match.get("department") or "Engineering").lower()

        raw_cand_skills = resume_json.get("skills") or best_match.get("matched_skills") or []
        if isinstance(raw_cand_skills, list):
            candidate_skills = [s for s in raw_cand_skills if isinstance(s, str)]
        elif isinstance(raw_cand_skills, dict):
            candidate_skills = [s for sub in raw_cand_skills.values() if isinstance(sub, list) for s in sub if isinstance(s, str)]
        else:
            candidate_skills = []

        # 1. Best Vacancies for Candidate (Deterministic Scoring Engine authority)
        suitable_openings = match_analysis.get("suitable_openings") or []
        best_vacancies = []
        for vac in suitable_openings[:5]:
            if isinstance(vac, dict):
                best_vacancies.append({
                    "vacancy_id": vac.get("vacancy_id") or vac.get("id"),
                    "job_title": vac.get("job_title"),
                    "department": vac.get("department") or vac.get("department_name"),
                    "score": vac.get("score") or vac.get("overall_score"),
                    "classification": vac.get("classification"),
                    "recommendation": vac.get("recommendation"),
                    "reason": vac.get("ranking_reason") or vac.get("reason"),
                })

        # 2. Related Skills Recommendations (via DomainEmbeddingService)
        related_skills_set = set()
        for skill in candidate_skills[:5]:
            eqs = DomainEmbeddingService.find_semantic_equivalents(term=skill, category="skills", limit=3)
            for eq in eqs:
                eq_term = eq["term"].title()
                if eq_term.lower() not in [s.lower() for s in candidate_skills]:
                    related_skills_set.add(eq_term)

        related_skills = list(related_skills_set)[:8]

        # 3. Missing Qualifications & Skill Gap Insights
        missing_quals = []
        if best_match:
            missing_skills = best_match.get("missing_skills") or []
            missing_criteria = best_match.get("missing_criteria") or []
            for ms in missing_skills[:5]:
                missing_quals.append({
                    "requirement": f"Missing Skill: {ms}",
                    "impact": "Required to achieve HIGH match score on top vacancy",
                    "type": "Skill",
                })
            for mc in missing_criteria[:3]:
                if not any(ms in mc for ms in missing_skills):
                    missing_quals.append({
                        "requirement": mc,
                        "impact": "Improves overall candidate match suitability",
                        "type": "Criterion",
                    })

        # 4. Recommended Certifications
        recommended_certs = []
        for dept_key, cert_list in cls.DEPARTMENT_CERTIFICATION_MAP.items():
            if dept_key in primary_dept or primary_dept in dept_key:
                recommended_certs.extend(cert_list)

        if not recommended_certs:
            recommended_certs = ["AWS Certified Solutions Architect", "PMP Certification", "Scrum Master (PSM I)"]

        # 5. Career Transition Opportunities
        career_transitions = []
        cand_role = (best_match.get("job_title") or "Software Engineer").lower()
        for role_key, target_roles in cls.CAREER_TRANSITION_MAP.items():
            if role_key in cand_role or cand_role in role_key:
                for target_role in target_roles:
                    career_transitions.append({
                        "target_role": target_role,
                        "transferable_skills": candidate_skills[:3],
                        "feasibility_score": 85.0,
                        "growth_note": f"Strong transferable foundation in {', '.join(candidate_skills[:2])}.",
                    })

        if not career_transitions:
            career_transitions.append({
                "target_role": "DevOps Engineer",
                "transferable_skills": candidate_skills[:3],
                "feasibility_score": 80.0,
                "growth_note": "High demand role with overlapping technical foundation.",
            })

        # 6. Internal Talent Pools
        exp_years = r.get("quality_metrics", {}).get("experience_years") or 0.0
        exp_tier = "Senior" if exp_years >= 5.0 else ("Mid-Level" if exp_years >= 2.0 else "Junior")
        talent_pools = [
            f"{primary_dept.title()} - {exp_tier} Pool",
            f"Core {candidate_skills[0] if candidate_skills else 'Tech'} Specialists",
        ]

        return {
            "candidate_id": cv_key,
            "full_name": extracted_name,
            "primary_department": primary_dept.title(),
            "best_vacancies": best_vacancies,
            "related_skills": related_skills,
            "missing_qualifications": missing_quals,
            "recommended_certifications": list(set(recommended_certs))[:4],
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
