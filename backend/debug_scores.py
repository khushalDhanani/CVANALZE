import pytest
import asyncio
from app.services.match_service import MatchService

@pytest.mark.asyncio
async def test_debug():
    software_cv = """
    Sarah Developer
    Senior Full Stack & Mobile Engineer
    Skills: Flutter, Dart, React Native, REST APIs, Python, Git
    Experience: 4 years software development
    """
    matching_vacancies = [
        {
            "id": 301,
            "vacancy_id": 301,
            "title": "Mobile App Developer",
            "department": "Information Technology",
            "department_name": "Information Technology",
            "required_skills": ["Flutter", "Dart", "REST APIs"],
            "min_experience_years": 2,
        }
    ]

    analysis = await MatchService.analyze_single_cv(
        cv_text=software_cv,
        job_openings=matching_vacancies,
        document_hash="doc_test_genuine_111",
        candidate_id="cand_test_genuine_111",
    )
    if analysis.best_match:
        m = analysis.best_match
        print("Final Score:", m.overall_score)
        print("Role Score:", m.role_score)
        print("Skills Score:", m.skills_score)
        print("Domain Score:", m.domain_score)
        print("Raw Score:", m.score)
        print("Failures:", [f.description for f in m.mandatory_failures] if m.mandatory_failures else "None")
        # print("is_cross_domain:", m.is_cross_domain)
        print("domain_mismatch_capped:", getattr(m, 'domain_mismatch_capped', None))
        sb = getattr(m, 'score_breakdown', None)
        print("is_hierarchy_valid:", sb.is_hierarchy_valid if sb else "Unknown")
        print("has_genuine_match:", analysis.has_genuine_match)

