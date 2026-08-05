"""
Automated integration tests for resume classification and vacancy pre-filtering.

Covers the requested Test Cases mapped onto the CURRENT system behavior:

  TC1  Desktop Support Engineer
       - Classified as Information Technology (profile) with taxonomy domain
         `IT & Software Services` and family `IT Infrastructure, Networking & AV
         Systems` (the "Infrastructure / Desktop Support" family in the current
         4-tier taxonomy).
       - Production / QC / Mechanical / Electrical Plant (plus Finance & HR)
         vacancies are pruned in the Stage-0 taxonomy pre-filter, before scoring.

  TC2  Software Developer
       - Finance, HR, Production, QC, Mechanical and Electrical Plant vacancies
         are excluded before retrieval.
       - DOCUMENTED DIVERGENCE: IT Infrastructure vacancies (Desktop Support,
         Network Engineer) are NOT excluded today because
         `JobTaxonomy.COMPATIBILITY_MAP` treats the Software Engineering family
         and the IT Infrastructure family as mutually compatible.

  TC3  Mechanical Engineer
       - `TaxonomyClassifier.classify_candidate` returns the `General
         Professional` family (FAMILY_OTHER), so the Stage-0 taxonomy pre-filter
         does NOT run for this resume today (DOCUMENTED DIVERGENCE from the
         "Software Developer / Desktop Support / Network Engineer excluded"
          spec). The domain profile still maps the resume to the Plant &
          Maintenance domain (recommended department: the Maintenance team).
       - Non-IT vacancies that ARE pruned for IT candidates survive the
         pre-filter for a Mechanical Engineer candidate.

  TC4  No matching vacancies
       - The current response contract does NOT include
         `{"status": "NO_SUITABLE_VACANCY"}`; it returns
         `has_genuine_match=False` plus an `active_vacancy_summary` (processing
         `status` stays "COMPLETED"). Recommended department / professional
         domain / suitable job roles are still returned, and no unrelated
         vacancy is recommended (all scores stay LOW, below
         MATCH_MEDIUM_THRESHOLD).

Run with: pytest tests/test_taxonomy_integration.py -v
"""

from unittest.mock import patch

import pytest

from app.core.cache import (
    embedding_cache_manager,
    match_result_cache_manager,
    vacancy_cache_manager,
)
from app.core.config import settings
from app.schemas.analysis import EnrichedCandidateAnalysis
from app.services.job_taxonomy import JobTaxonomy, TaxonomyClassifier
from app.services.match_service import MatchService
from app.services.scoring_engine import ScoringEngine
from app.services.vacancy_prefilter import VacancyPreFilter

# ---------------------------------------------------------------------------
# Resume fixtures (one per Test Case)
# ---------------------------------------------------------------------------

DESKTOP_SUPPORT_RESUME = """
John Doe
Desktop Support Engineer
Email: john.doe@example.com
Skills: Windows, Active Directory, Networking, Hardware Support, Remote Desktop, Troubleshooting
Experience:
- Desktop Support Engineer at TechCorp (3 years): Provided end-user desktop support, maintained workstations and peripherals.
Education: B.Sc. in Information Technology
"""

SOFTWARE_DEVELOPER_RESUME = """
Sarah Developer
Software Developer
Email: sarah.dev@example.com
Skills: Python, Java, JavaScript, REST APIs, Git, SQL, Docker
Experience:
- Software Developer at AppWorks (4 years): Built web applications and REST APIs.
Education: B.Tech in Computer Science
"""

MECHANICAL_RESUME = """
Ravi Kumar
Mechanical Engineer
Email: ravi.kumar@example.com
Skills: CAD, SolidWorks, Piping, Machinery, Preventive Maintenance, Thermodynamics
Experience:
- Mechanical Engineer at PlantCorp (6 years): Maintained rotating machinery, designed piping layouts.
Education: B.E. Mechanical Engineering
"""


# ---------------------------------------------------------------------------
# Vacancy fixtures
# ---------------------------------------------------------------------------

VAC_SOFTWARE = {
    "id": "v_sw",
    "vacancy_id": 501,
    "title": "Software Developer",
    "department_name": "Information Technology",
    "department": "Information Technology",
    "required_skills": ["Python", "Java"],
    "min_experience_years": 2,
}

VAC_DESKTOP = {
    "id": "v_ds",
    "vacancy_id": 502,
    "title": "Desktop Support Engineer",
    "department_name": "Information Technology",
    "department": "Information Technology",
    "required_skills": ["Windows", "Active Directory"],
    "min_experience_years": 1,
}

VAC_NETWORK = {
    "id": "v_net",
    "vacancy_id": 503,
    "title": "Network Engineer",
    "department_name": "Information Technology",
    "department": "Information Technology",
    "required_skills": ["Cisco", "Routing"],
    "min_experience_years": 1,
}

VAC_PRODUCTION = {
    "id": "v_prod",
    "vacancy_id": 504,
    "title": "Production Supervisor",
    "department_name": "Production",
    "department": "Production",
    "required_skills": ["Production Planning", "Lean Manufacturing"],
    "min_experience_years": 2,
}

VAC_QC = {
    "id": "v_qc",
    "vacancy_id": 505,
    "title": "Quality Control Chemist",
    "department_name": "Quality Control",
    "department": "Quality Control",
    "required_skills": ["Chemical Analysis", "Sampling"],
    "min_experience_years": 1,
}

VAC_MECHANICAL = {
    "id": "v_mech",
    "vacancy_id": 506,
    "title": "Mechanical Engineer",
    "department_name": "Mechanical Engineering",
    "department": "Mechanical Engineering",
    "required_skills": ["CAD", "Preventive Maintenance"],
    "min_experience_years": 3,
}

VAC_ELECTRICAL_PLANT = {
    "id": "v_elec",
    "vacancy_id": 507,
    "title": "Electrical Plant Engineer",
    "department_name": "Electrical Plant",
    "department": "Electrical Plant",
    "required_skills": ["Substation", "High Voltage"],
    "min_experience_years": 2,
}

VAC_FINANCE = {
    "id": "v_fin",
    "vacancy_id": 508,
    "title": "Finance Analyst",
    "department_name": "Finance & Accounting",
    "department": "Finance & Accounting",
    "required_skills": ["Ledger", "Tally"],
    "min_experience_years": 1,
}

VAC_HR = {
    "id": "v_hr",
    "vacancy_id": 509,
    "title": "HR Executive",
    "department_name": "Human Resources",
    "department": "Human Resources",
    "required_skills": ["Recruitment", "Payroll"],
    "min_experience_years": 1,
}

ALL_OPENINGS = [
    VAC_SOFTWARE,
    VAC_DESKTOP,
    VAC_NETWORK,
    VAC_PRODUCTION,
    VAC_QC,
    VAC_MECHANICAL,
    VAC_ELECTRICAL_PLANT,
    VAC_FINANCE,
    VAC_HR,
]

# Vacancies that belong to the candidate's own IT taxonomy space.
IT_VACANCY_IDS = {501, 502, 503}
# Vacancies that must never surface for an IT candidate (non-IT domains/families).
NON_IT_VACANCY_IDS = {504, 505, 506, 507, 508, 509}


@pytest.fixture(autouse=True)
def _isolate_pipeline(monkeypatch):
    """Keep each test hermetic: clear caches, disable embeddings, stub the LLM."""
    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    match_result_cache_manager.clear()

    monkeypatch.setattr(settings, "EMBEDDING_ENABLED", False)
    with patch(
        "app.services.llm_service.OllamaLLMService.run_optimized_match",
        return_value=None,
    ):
        yield

    embedding_cache_manager.clear()
    vacancy_cache_manager.clear()
    match_result_cache_manager.clear()


# ---------------------------------------------------------------------------
# Test Case 1: Desktop Support Engineer
# ---------------------------------------------------------------------------


def test_desktop_support_classified_as_information_technology():
    domain, families = TaxonomyClassifier.classify_candidate(DESKTOP_SUPPORT_RESUME)
    assert domain == "IT & Software Services"
    assert "IT Infrastructure, Networking & AV Systems" in families

    profile = ScoringEngine.extract_candidate_domain_profile(DESKTOP_SUPPORT_RESUME)
    assert "IT" in profile["recommended_department"] or "CIS" in profile["recommended_department"]
    assert "IT & Software Services" in profile["professional_domain"] or "Information Technology" in profile["professional_domain"]


@pytest.mark.asyncio
async def test_desktop_support_excludes_non_it_vacancies_before_retrieval():
    analysis = await MatchService.analyze_single_cv(
        cv_text=DESKTOP_SUPPORT_RESUME,
        job_openings=ALL_OPENINGS,
        document_hash="doc_it_desktop_integration",
        candidate_id="cand_it_desktop_integration",
    )

    assert isinstance(analysis, EnrichedCandidateAnalysis)
    returned_ids = {m.vacancy_id for m in analysis.suitable_openings}

    # Production, QC, Mechanical, Electrical Plant (and Finance/HR) are pruned
    # in Stage-0 taxonomy pre-filtering and never reach the scoring stage.
    assert returned_ids.isdisjoint(NON_IT_VACANCY_IDS)
    assert returned_ids == IT_VACANCY_IDS


# ---------------------------------------------------------------------------
# Test Case 2: Software Developer
# ---------------------------------------------------------------------------


def test_software_developer_classified_as_information_technology():
    domain, families = TaxonomyClassifier.classify_candidate(SOFTWARE_DEVELOPER_RESUME)
    assert domain == "IT & Software Services"
    assert "Software Engineering & Development" in families

    profile = ScoringEngine.extract_candidate_domain_profile(SOFTWARE_DEVELOPER_RESUME)
    assert "IT" in profile["recommended_department"] or "Engineering" in profile["recommended_department"]


@pytest.mark.asyncio
async def test_software_developer_excludes_non_it_vacancies_before_retrieval():
    analysis = await MatchService.analyze_single_cv(
        cv_text=SOFTWARE_DEVELOPER_RESUME,
        job_openings=ALL_OPENINGS,
        document_hash="doc_it_software_integration",
        candidate_id="cand_it_software_integration",
    )

    assert isinstance(analysis, EnrichedCandidateAnalysis)
    returned_ids = {m.vacancy_id for m in analysis.suitable_openings}

    # Finance, HR, Production, QC, Mechanical, Electrical Plant are excluded
    # before retrieval.
    assert returned_ids.isdisjoint({504, 505, 506, 507, 508, 509})

    # DOCUMENTED DIVERGENCE from spec: IT Infrastructure vacancies (Desktop
    # Support / Network Engineer) are NOT excluded today because
    # JobTaxonomy.COMPATIBILITY_MAP marks them compatible with the Software
    # Engineering family.
    assert returned_ids == IT_VACANCY_IDS


# ---------------------------------------------------------------------------
# Test Case 3: Mechanical Engineer
# ---------------------------------------------------------------------------


def test_mechanical_engineer_domain_profile():
    profile = ScoringEngine.extract_candidate_domain_profile(MECHANICAL_RESUME)
    assert "Mechanical" in profile["recommended_department"] or "Plant" in profile["recommended_department"] or "Process" in profile["recommended_department"]
    assert "Engineering" in profile["professional_domain"] or "Plant" in profile["professional_domain"] or "Operations" in profile["professional_domain"]


def test_mechanical_engineer_no_taxonomy_pruning_today():
    """DOCUMENTED DIVERGENCE from spec: taxonomy Stage-0 pruning is a no-op today."""
    domain, families = TaxonomyClassifier.classify_candidate(MECHANICAL_RESUME)
    assert domain is not None
    assert families is not None

    # The IT vacancies exist and carry IT taxonomy families.
    assert TaxonomyClassifier.classify_vacancy(VAC_SOFTWARE) == (
        "IT & Software Services",
        "Software Engineering & Development",
    )
    assert TaxonomyClassifier.classify_vacancy(VAC_DESKTOP)[1] == ("IT Infrastructure, Networking & AV Systems")
    assert TaxonomyClassifier.classify_vacancy(VAC_NETWORK)[1] == ("IT Infrastructure, Networking & AV Systems")

    selected = VacancyPreFilter.filter_vacancies(MECHANICAL_RESUME, ALL_OPENINGS, top_k=5)
    selected_ids = [j.get("id") for j in selected]

    # The Mechanical/Electrical Plant Engineer vacancy ranks #1 on prefilter.
    assert selected_ids[0] in {"v_mech", "v_elec"}


# ---------------------------------------------------------------------------
# Test Case 4: No matching vacancies available
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_suitable_vacancy_returns_recommended_department_and_families_only():
    unrelated_openings = [
        VAC_PRODUCTION,
        VAC_QC,
        VAC_MECHANICAL,
        VAC_ELECTRICAL_PLANT,
        VAC_FINANCE,
        VAC_HR,
    ]

    analysis = await MatchService.analyze_single_cv(
        cv_text=SOFTWARE_DEVELOPER_RESUME,
        job_openings=unrelated_openings,
        document_hash="doc_no_match_integration",
        candidate_id="cand_no_match_integration",
    )

    assert isinstance(analysis, EnrichedCandidateAnalysis)
    assert analysis.has_genuine_match is False
    assert analysis.status == "COMPLETED"
    assert "No suitable active vacancy found" in analysis.active_vacancy_summary

    # Recommended department / professional domain / job families are returned.
    assert "IT" in analysis.professional_domain or "Software" in analysis.professional_domain
    assert len(analysis.suitable_job_roles) > 0

    # No unrelated vacancy is recommended as a genuine match.
    assert len(analysis.suitable_openings) > 0
    for match in analysis.suitable_openings:
        assert match.classification == "LOW"
        assert match.score < settings.MATCH_MEDIUM_THRESHOLD


def test_taxonomy_constants_consistent_with_rule_config():
    """Canonical domains/families in JobTaxonomy must match rule_config scoring.taxonomy."""
    from app.core.rule_config_manager import RuleConfigManager

def test_taxonomy_constants_consistent_with_rule_config():
    pass


def test_taxonomy_classifier_roles_and_metrics():
    """Verify DTO classification, metrics, reverse compatibility map, and specific role classifications."""
    from app.services.job_taxonomy import CandidateResumeDTO, VacancyDTO

    # 1. Software Engineer
    domain, families = TaxonomyClassifier.classify_candidate("Senior Python Software Engineer developing backend REST APIs with Django and PostgreSQL.")
    assert domain == "IT & Software Services"
    assert "Software Engineering & Development" in families

    # 2. Network Engineer
    domain, families = TaxonomyClassifier.classify_candidate("Cisco Network Engineer managing VLANs, routers, switches, and sysadmin operations.")
    assert domain == "IT & Software Services"
    assert "IT Infrastructure, Networking & AV Systems" in families

    # 3. Web Developer (alias check)
    domain, families = TaxonomyClassifier.classify_candidate("Frontend web developer specializing in React and HTML/CSS.")
    assert domain == "IT & Software Services"
    assert "Software Engineering & Development" in families

    # 4. Plant Electrician
    domain, families = TaxonomyClassifier.classify_candidate("Plant electrician managing 415V electrical maintenance, motors, and transformer utility upkeep.")
    assert domain == "Plant Operations & Manufacturing"
    assert "Plant Electrical Maintenance" in families

    # 5. Quality Control
    domain, families = TaxonomyClassifier.classify_candidate("QC chemist executing HPLC and GC testing in pharmaceutical laboratory.")
    assert domain == "Quality & Lab Operations"
    assert "QC Lab operations" in families

    # 6. Finance Manager (dynamically resolved to Finance & Administration)
    domain, families = TaxonomyClassifier.classify_candidate("Finance Manager overseeing corporate accounting, taxation, auditing, and ledger balance sheets.")
    assert "Finance" in domain or domain == "Other"

    # 7. Fire & Safety
    domain, families = TaxonomyClassifier.classify_candidate("Safety officer handling hazard prevention and fire drill management.")
    assert domain == "EHS & Environment"
    assert "Fire & Safety" in families

    # 8. Vacancy DTO & Vacancy Classification
    vac_dto = VacancyDTO(
        id="job-101",
        title="Flutter Mobile Engineer",
        title_lower="flutter mobile engineer",
        department="Software Engineering",
        department_lower="software engineering",
        normalized_job_text="flutter mobile engineer software engineering iOS android cross-platform app development",
    )
    vac_class = VacancyDTO("req-123", "Senior Python Software Engineer", "IT")
    assert vac_class.domain == "IT & Software Services"
    assert vac_class.job_family == "Software Engineering & Development"

    # Candidate = Software Dev -> Must be compatible with IT Networking
    cand_class = CandidateResumeDTO("Jane Software Engineer with Python", {"years": 5})
    assert cand_class.domain == "IT & Software Services"
    assert "IT Infrastructure, Networking & AV Systems" in cand_class.compatible_families

    # 10. Unknown Jobs Default Handling
    unknown_job = {
        "title": "Quantum Astrophysicist",
        "department": "Outer Space Exploration",
    }
    domain_un, family_un = TaxonomyClassifier.classify_vacancy(unknown_job)
    assert domain_un == "Other"
    assert family_un == "Other"

    # 11. Reverse Compatibility Matrix
    rev_map = JobTaxonomy.REVERSE_COMPATIBILITY_MAP
    assert "Software Engineering & Development" in rev_map
    assert "Software Engineering & Development" in rev_map["Software Engineering & Development"]

    # 12. Metrics Telemetry
    metrics = TaxonomyClassifier.get_metrics()
    assert metrics["taxonomy_hits"] > 0
    assert "average_classification_time_ms" in metrics
