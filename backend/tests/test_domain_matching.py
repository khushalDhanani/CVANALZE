import pytest

from app.schemas.analysis import EnrichedCandidateAnalysis
from app.services.match_service import MatchService
from app.services.scoring_engine import ScoringEngine


def test_extract_candidate_domain_profile_software():
    cv_text = """
    Jane Doe
    Email: jane.doe@example.com
    Title: Senior Flutter & Mobile App Developer
    Skills: Flutter, Dart, React Native, REST APIs, Git, State Management, Firebase
    Education: B.Tech in Computer Science & Engineering
    Experience:
    - Senior Mobile App Engineer at TechCorp (3 years): Built cross-platform mobile apps for Android and iOS using Flutter.
    Projects:
    - E-Commerce Mobile App: Developed complete shopping experience in Flutter with RESTful backend integration.
    """
    profile = ScoringEngine.extract_candidate_domain_profile(cv_text)
    assert "Software" in profile["recommended_department"] or "CIS" in profile["recommended_department"] or "IT" in profile["recommended_department"]
    assert "Software" in profile["professional_domain"] or "IT" in profile["professional_domain"]
    assert len(profile["strengths"]) > 0
    assert any("Flutter" in role or "Developer" in role or "Software" in role or "Engineer" in role for role in profile["suitable_job_roles"])


def test_extract_candidate_domain_profile_finance():
    cv_text = """
    John Smith
    Financial Analyst | CA Inter
    Skills: Financial Modeling, Valuation, Ledger, Tally ERP, Tax Audit, Forecasting, Excel
    Education: Bachelor of Commerce (B.Com) in Accounting & Finance
    Experience:
    - Senior Financial Analyst at FinGroup (4 years): Prepared quarterly financial balance sheets and tax audits.
    """
    profile = ScoringEngine.extract_candidate_domain_profile(cv_text)
    assert "Finance" in profile["recommended_department"] or "Accounts" in profile["recommended_department"]
    assert "Finance" in profile["professional_domain"] or "Accounting" in profile["professional_domain"]
    assert len(profile["suitable_job_roles"]) > 0


def test_domain_mismatch_penalty_software_vs_plant(monkeypatch):
    from app.services.job_taxonomy import TaxonomyClassifier
    monkeypatch.setattr(TaxonomyClassifier, "classify_vacancy", lambda *args, **kwargs: ("Engineering", "Mechanical"))
    monkeypatch.setattr(TaxonomyClassifier, "classify_candidate", lambda *args, **kwargs: ("IT", ("Software Engineering",)))
    cv_text = """
    Alex Engineer
    Senior Software & Mobile Developer
    Skills: Flutter, Dart, Python, FastAPI, PostgreSQL, Docker
    Education: B.E. in Computer Science
    """
    plant_job = {
        "id": "101",
        "title": "Plant Assistant",
        "department": "Plant & Maintenance",
        "department_name": "Plant & Maintenance",
        "required_skills": [
            "Boiler Operation",
            "Mechanical Fitting",
            "Equipment Maintenance",
        ],
        "min_experience_years": 1,
    }

    match_result = ScoringEngine.evaluate_job_match(cv_text, plant_job)
    assert match_result.score < 25.0
    assert any(f.requirement_id == "req_domain_mismatch" for f in match_result.mandatory_failures)


@pytest.mark.asyncio
async def test_no_suitable_active_vacancy_summary():
    software_cv = """
    Dev Smith
    Flutter App Developer
    Skills: Flutter, Dart, Firebase, REST APIs, Mobile Development
    Experience: 3 years mobile developer
    """
    unrelated_vacancies = [
        {
            "id": 201,
            "vacancy_id": 201,
            "title": "Plant Assistant",
            "department": "Plant & Maintenance",
            "department_name": "Plant & Maintenance",
            "required_skills": ["Boiler Maintenance", "Piping"],
        },
        {
            "id": 202,
            "vacancy_id": 202,
            "title": "Chemist",
            "department": "Quality & Safety",
            "department_name": "Quality & Safety",
            "required_skills": ["Chemical Analysis", "Lab Testing"],
        },
    ]

    analysis = await MatchService.analyze_single_cv(
        cv_text=software_cv,
        job_openings=unrelated_vacancies,
        document_hash="doc_test_unrelated_123",
        candidate_id="cand_test_unrelated_123",
    )

    assert isinstance(analysis, EnrichedCandidateAnalysis)
    assert analysis.has_genuine_match is False
    assert "No suitable active vacancy found" in analysis.active_vacancy_summary
    assert any(term in analysis.recommended_department for term in ["IT & Software Services", "Software", "CIS"])
    assert len(analysis.ai_career_summary) > 0


@pytest.mark.asyncio
async def test_genuine_active_vacancy_match():
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
        document_hash="doc_test_genuine_456",
        candidate_id="cand_test_genuine_456",
    )

    assert isinstance(analysis, EnrichedCandidateAnalysis)
    assert analysis.has_genuine_match is True
    assert "Genuine Match Found" in analysis.active_vacancy_summary
    assert analysis.best_match.job_title == "Mobile App Developer"
    assert len(analysis.ai_career_summary) > 0
