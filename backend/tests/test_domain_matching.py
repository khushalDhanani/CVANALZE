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


def test_cross_domain_guard_caps_it_candidate_vs_non_it_vacancy_with_unknown_taxonomy():
    """IT candidate matched to a QC vacancy with Unknown taxonomy metadata must be
    capped — the guard flags computed in job_context must actually be consumed."""
    from app.schemas.candidate_context import CandidateAnalysisContext
    from app.schemas.job_context import JobEvaluationContext
    from app.services.match_evaluators import CrossDomainGuardEvaluator

    context = CandidateAnalysisContext(
        cv_text="Software Engineer",
        norm_text="software engineer flutter dart",
        is_software_cand=True,
        cand_tax_domain="Information Technology",
        cand_families=["Software Engineering & Development"],
        cand_primary_family="Software Engineering & Development",
        cand_domain="IT",
    )

    qc_job = JobEvaluationContext.create(
        {
            "id": "1195",
            "title": "Lab Assistant - I (QC)",
            "department": "Quality Control Team",
            "department_name": "Quality Control Team",
            "required_skills": ["HPLC", "Laboratory knowledge", "Chemical analysis"],
            "_precomputed_domain": "Unknown",
            "_precomputed_job_family": "Unknown",
        }
    )

    result = CrossDomainGuardEvaluator.evaluate(
        context,
        qc_job,
        initial_score=85.0,
        initial_domain_score=80.0,
        reason_str="",
        mandatory_failures=[],
    )

    assert result.is_domain_capped is True
    assert result.final_score < 85.0
    assert any(f.requirement_id == "req_domain_mismatch" for f in result.additional_mandatory_failures)


def test_cross_domain_guard_does_not_cap_software_vacancy():
    """A genuine software vacancy (has_software_req / IT department) must not be capped."""
    from app.schemas.candidate_context import CandidateAnalysisContext
    from app.schemas.job_context import JobEvaluationContext
    from app.services.match_evaluators import CrossDomainGuardEvaluator

    context = CandidateAnalysisContext(
        cv_text="Software Engineer",
        norm_text="software engineer flutter dart",
        is_software_cand=True,
        cand_tax_domain="Information Technology & Software",
        cand_families=["Software Engineering & Development"],
        cand_primary_family="Software Engineering & Development",
        cand_domain="Information Technology & Software",
    )

    sw_job = JobEvaluationContext.create(
        {
            "id": "1334",
            "title": "Software Developer",
            "department": "CIS Team",
            "department_name": "CIS Team",
            "required_skills": [".NET", "SQL", "LINQ", "ADO.NET"],
            "_precomputed_domain": "Unknown",
            "_precomputed_job_family": "Unknown",
        }
    )

    result = CrossDomainGuardEvaluator.evaluate(
        context,
        sw_job,
        initial_score=90.0,
        initial_domain_score=85.0,
        reason_str="",
        mandatory_failures=[],
    )

    assert result.is_domain_capped is False
    assert result.final_score == 90.0


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
