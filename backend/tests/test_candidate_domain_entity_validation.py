from types import SimpleNamespace
from unittest.mock import patch

from app.repositories.department_domain import DepartmentDomainRepository
from app.schemas.analysis import OptimizedCandidateProfile
from app.schemas.classification_types import MatchStatus
from app.schemas.domain import DepartmentDomain
from app.services.candidate_domain_service import CandidateDomainService
from app.services.llm_grounding_service import LLMGroundingService
from app.services.resume_field_extractor import ResumeFieldExtractor


def _finance_repository() -> DepartmentDomainRepository:
    repository = DepartmentDomainRepository(db_factory=lambda: None)
    domains = [
        DepartmentDomain(
            id=1,
            department_id=10,
            department_name="Finance",
            domain_name="Finance & Accounting",
            keywords=["financial analysis", "financial modeling", "forecasting", "accounting", "python", "sql"],
            default_roles=["Financial Analyst", "Accountant"],
            priority=1,
        )
    ]
    repository._domains = domains
    repository._matchers = repository._build_matchers(domains)
    return repository


def test_inline_skill_section_does_not_fall_back_to_personal_cv_text():
    resume = ResumeFieldExtractor.extract(
        """
        A Candidate Name
        Phone: +91 98765 43210
        Date of Birth: 08/04/2000
        Skills: Python, SQL, Financial Modeling
        Experience: Financial Analyst
        2017 - 2022
        """
    )

    assert resume["skills"]["all_skills"] == ["Python", "SQL", "Financial Modeling"]


def test_hiring_intelligence_rejects_cross_type_and_cross_section_contamination():
    cv_text = """
    Patel Urjitkumar Rakeshbhai
    Near Avdhut Temple, Example City
    Personal Details
    Date of Birth: 08/04/2000
    Phone: +91 98765 43210
    ## Skills
    Python, SQL, Financial Modeling, 12, 2017, 2020, 2022
    ## Work Experience
    Financial Analyst
    Acme Holdings
    2017 - 2022
    Prepared financial forecasts and financial analysis reports using Python and SQL.
    """
    contaminated_resume = {
        "contact_info": {
            "name": "Patel Urjitkumar Rakeshbhai",
            "location": "Near Avdhut Temple, Example City",
            "phone": "+91 98765 43210",
        },
        "skills": {
            "all_skills": ["08/04/2000", "12", "2017", "2020", "2022", "Python", "SQL", "Financial Modeling"],
        },
        "work_experience": [
            {"job_title": "Patel Urjitkumar Rakeshbhai"},
            {"job_title": "Near Avdhut Temple, Example City"},
            {"job_title": "Skills"},
            {"job_title": "Personal Details"},
            {
                "job_title": "Financial Analyst",
                "company": "Acme Holdings",
                "responsibilities": ["Prepared financial forecasts and financial analysis reports using Python and SQL."],
            },
        ],
    }
    llm_profile = OptimizedCandidateProfile(
        core_skills=["08/04/2000", "2022", "Python"],
        current_role="Patel Urjitkumar Rakeshbhai",
        suitable_job_roles=["Near Avdhut Temple, Example City", "Skills"],
    )

    with patch(
        "app.services.candidate_domain_service.DynamicTaxonomyService.resolve_candidate_role_and_domain",
        return_value=SimpleNamespace(match_status=MatchStatus.NO_SUITABLE_MATCH),
    ):
        profile = CandidateDomainService.extract_candidate_domain_profile(
            cv_text,
            optimized_profile=llm_profile,
            resume_json=contaminated_resume,
            domain_repository=_finance_repository(),
        )

    assert profile["suitable_job_roles"] == ["Financial Analyst"]
    assert profile["strengths"][0] == "Core Skills: Financial Modeling, Python, SQL"
    rendered = " ".join([*profile["strengths"], *profile["suitable_job_roles"]])
    for contaminant in (
        "08/04/2000",
        "12",
        "2017",
        "2020",
        "2022",
        "Patel Urjitkumar Rakeshbhai",
        "Near Avdhut Temple",
        "Skills",
        "Personal Details",
        "Acme Holdings",
    ):
        assert contaminant not in rendered


def test_uncorroborated_entities_are_excluded_instead_of_inferred():
    cv_text = "## Experience\nFinancial Analyst\nPrepared financial forecasts and accounting reports."
    resume = {
        "skills": {"all_skills": ["Unmentioned Competency"]},
        "work_experience": [{"job_title": "Unmentioned Occupation"}],
    }

    with patch(
        "app.services.candidate_domain_service.DynamicTaxonomyService.resolve_candidate_role_and_domain",
        return_value=SimpleNamespace(match_status=MatchStatus.NO_SUITABLE_MATCH),
    ):
        profile = CandidateDomainService.extract_candidate_domain_profile(
            cv_text,
            resume_json=resume,
            domain_repository=_finance_repository(),
        )

    assert "Unmentioned Competency" not in " ".join(profile["strengths"])
    assert "Unmentioned Occupation" not in profile["suitable_job_roles"]


def test_llm_grounding_requires_semantic_type_not_only_text_presence():
    cv_text = """
    Patel Urjitkumar Rakeshbhai
    Near Avdhut Temple, Example City
    Date of Birth: 08/04/2000
    ## Skills
    Python, 2022
    ## Work Experience
    Financial Analyst
    """

    with patch("app.services.candidate_domain_service.department_domain_repository", _finance_repository()):
        skills, skill_count, _ = LLMGroundingService._filter_skills(["08/04/2000", "2022", "Python"], cv_text)
        roles, role_count, _ = LLMGroundingService._filter_roles(
            ["Patel Urjitkumar Rakeshbhai", "Near Avdhut Temple, Example City", "Skills", "Financial Analyst"],
            cv_text,
        )

    assert skills == ["Python"]
    assert skill_count == 1
    assert roles == ["Financial Analyst"]
    assert role_count == 1
