import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.cache import CacheKey
from app.repositories.department_domain import DepartmentDomainRepository
from app.schemas.classification_types import MatchStatus
from app.schemas.domain import DepartmentDomain
from app.services.candidate_domain_service import CandidateDomainService
from app.services.experience_calculator import ExperienceCalculator
from app.services.match_evaluators import VacancyFitEvaluator
from app.services.matching_quality_gate import MatchingQualityGate
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.scoring_engine import ScoringEngine


FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "matching_quality" / "regression_cvs.json").read_text()
)


def _software_taxonomy_repository() -> DepartmentDomainRepository:
    repository = DepartmentDomainRepository(db_factory=lambda: None)
    domains = [
        DepartmentDomain(
            id=1,
            department_id=9,
            department_name="CIS Team",
            domain_name="Information Technology",
            keywords=[
                "software developer", "developer", "frontend", "react", "javascript", "typescript",
                "flutter", "dart", "firebase", "asp.net", ".net", "c#", "api development",
            ],
            default_roles=["Software Developer", "Frontend Developer", "Full Stack Developer", "Mobile Application Developer"],
            priority=1,
        )
    ]
    repository._domains = domains
    repository._matchers = repository._build_matchers(domains)
    return repository


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fixture: fixture["fixture_id"])
def test_regression_cv_extraction_evidence_and_experience(fixture):
    resume = ResumeFieldExtractor.extract(fixture["resume_text"], filename=f'{fixture["fixture_id"]}.pdf')
    name = resume["contact_info"]["name"]
    assert name.lower() == fixture["expected_name"].lower()
    assert name not in fixture.get("forbidden_names", [])

    extracted_skills = {skill.lower() for skill in resume["skills"]["all_skills"]}
    for skill in fixture["required_skills"]:
        assert any(skill.lower() in extracted or extracted in skill.lower() for extracted in extracted_skills)

    experience = ExperienceCalculator.calculate_canonical_experience(resume, fixture["resume_text"])
    assert experience["authoritative_years"] >= fixture["minimum_experience_years"]


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fixture: fixture["fixture_id"])
def test_regression_cv_software_family_outranks_unrelated_family(fixture):
    resume = ResumeFieldExtractor.extract(fixture["resume_text"])
    no_dynamic_match = SimpleNamespace(match_status=MatchStatus.NO_SUITABLE_MATCH)
    with patch(
        "app.services.candidate_domain_service.DynamicTaxonomyService.resolve_candidate_role_and_domain",
        return_value=no_dynamic_match,
    ):
        profile = CandidateDomainService.extract_candidate_domain_profile(
            fixture["resume_text"],
            resume_json=resume,
            domain_repository=_software_taxonomy_repository(),
        )
    assert any(term in profile["professional_domain"].lower() for term in ("software", "technology", "it"))


def test_missing_mandatory_skill_and_cross_domain_match_cannot_be_strong(monkeypatch):
    from app.services.job_taxonomy import TaxonomyClassifier

    monkeypatch.setattr(
        TaxonomyClassifier,
        "classify_candidate_with_confidence",
        lambda *args, **kwargs: ("IT", ["Software Engineering"], 1.0, MatchStatus.DB_MATCH, "test"),
    )
    monkeypatch.setattr(TaxonomyClassifier, "classify_vacancy", lambda job: ("Operations", "Plant Maintenance"))
    result = ScoringEngine.evaluate_job_match(
        "Flutter Developer. Skills: Flutter, Dart, Firebase. Experience: 6 years.",
        {
            "id": "plant-role",
            "title": "Plant Maintenance Engineer",
            "department": "Maintenance Team",
            "required_skills": ["Preventive Maintenance"],
            "required_skills_are_mandatory": True,
            "min_experience_years": 2.0,
        },
        candidate_experience=6.0,
    )
    assert result.mandatory_failures
    assert result.vacancy_match_status == "NO_STRONG_VACANCY_MATCH"
    assert not VacancyFitEvaluator.is_eligible_match(result)
    assert result.score == result.overall_score == result.vacancy_fit_score
    assert result.reason


def test_semantic_similarity_cannot_manufacture_skill_evidence(monkeypatch):
    from app.services.job_taxonomy import TaxonomyClassifier

    monkeypatch.setattr(
        TaxonomyClassifier,
        "classify_candidate_with_confidence",
        lambda *args, **kwargs: ("IT", ["Software Engineering"], 1.0, MatchStatus.DB_MATCH, "test"),
    )
    monkeypatch.setattr(TaxonomyClassifier, "classify_vacancy", lambda job: ("IT", "Software Engineering"))
    result = ScoringEngine.evaluate_job_match(
        "Front-end Developer. Skills: React, JavaScript, TypeScript.",
        {
            "id": "advisory-dotnet-role",
            "title": "Software Developer",
            "department": "CIS Team",
            "required_skills": [".NET Developer"],
            "required_skills_are_mandatory": False,
        },
        candidate_experience=3.0,
    )
    assert result.matched_skills == []
    assert result.missing_skills == [".NET Developer"]
    assert all("CV contains skill" not in item.cv_evidence for item in result.evidence.values())


def test_matching_cache_key_changes_with_rules_prompts_and_taxonomy():
    base = {
        "document_hash": "doc-hash",
        "vacancy_version": "vacancy-v1",
        "prompt_version": "prompt-v1",
        "matching_version": "matching-v1",
        "rule_version": "rules-v1",
        "taxonomy_version": "taxonomy-v1",
    }
    original = CacheKey.for_match_result(**base).to_key()
    for version_field in ("prompt_version", "matching_version", "rule_version", "taxonomy_version"):
        changed = dict(base)
        changed[version_field] += "-changed"
        assert CacheKey.for_match_result(**changed).to_key() != original


def test_quality_gate_fails_closed_when_prompt_or_taxonomy_is_missing(monkeypatch):
    from app.repositories.department_domain import department_domain_repository
    from app.services.prompt_service import PromptReadiness, PromptService

    monkeypatch.setattr(PromptService, "check_required_optimized_match_prompt", classmethod(lambda cls: PromptReadiness(False, "missing")))
    assert MatchingQualityGate.check_runtime_readiness().reason_code == "PROMPT_UNAVAILABLE"

    monkeypatch.setattr(PromptService, "check_required_optimized_match_prompt", classmethod(lambda cls: PromptReadiness(True, "READY")))
    monkeypatch.setattr(department_domain_repository, "is_ready", lambda: False)
    assert MatchingQualityGate.check_runtime_readiness().reason_code == "TAXONOMY_UNAVAILABLE"


def test_quality_gate_fails_closed_when_required_rule_assets_are_empty(monkeypatch):
    from app.services.prompt_service import PromptReadiness, PromptService
    from app.core.rule_config_manager import RuleConfigManager

    monkeypatch.setattr(PromptService, "check_required_optimized_match_prompt", classmethod(lambda cls: PromptReadiness(True, "READY")))
    monkeypatch.setattr(RuleConfigManager, "get_config", classmethod(lambda cls: object()))
    monkeypatch.setattr(
        RuleConfigManager,
        "get_term_matching_assets",
        classmethod(lambda cls: {"stop_phrases": frozenset(), "noise_words": frozenset(), "aliases": {}}),
    )
    assert MatchingQualityGate.check_runtime_readiness().reason_code == "RULE_CONFIG_INCOMPLETE"


@pytest.mark.parametrize(
    ("text", "email", "expected"),
    [
        (
            "## CONTACT\n9998209988\n## OW T A R U N GUPTAFULL STACK D E V E L O P E R PROFILE SUMMARY\ngtworks05@gmail.com",
            "gtworks05@gmail.com",
            "Tarun Gupta",
        ),
        (
            "## Utkarsh Patil\n## ASP .NET Developer\ncodewithprogrammer@gmail.com\n9870059553",
            "codewithprogrammer@gmail.com",
            "Utkarsh Patil",
        ),
        (
            "kolisantosh222@gmail.com\nPassionate Flutter Developer with 6 years of experience in mobile app development, specializing in cross-platform applications and scalable client solutions.\n## Professional Experience\n## Sr. Flutter Developer\n## Santosh Koli Sr. Flutter Developer",
            "kolisantosh222@gmail.com",
            "Santosh Koli",
        ),
    ],
)
def test_name_extraction_rejects_roles_and_recovers_merged_headers(monkeypatch, text, email, expected):
    from app.repositories.department_domain import department_domain_repository

    software_repo = _software_taxonomy_repository()
    monkeypatch.setattr(department_domain_repository, "get_all_domains", software_repo.get_all_domains)
    name, _, _, _ = ResumeFieldExtractor.extract_candidate_name(text.splitlines(), email, None, None)
    assert name == expected


def test_single_date_fragments_do_not_override_explicit_experience_claim():
    experience = ExperienceCalculator.calculate_canonical_experience(
        {"work_experience": [{"dates": "2024-04"}, {"dates": "2021-10"}]},
        "Passionate mobile developer with 6 years of experience.",
    )
    assert experience["deterministic_years"] is None
    assert experience["authoritative_years"] == 6.0
    assert experience["experience_state"] == "CLAIMED"


def test_iso_month_ranges_are_not_split_into_dates_and_fake_titles():
    resume = ResumeFieldExtractor.extract(
        """## Professional Experience
## Sr. Flutter Developer
Resonent TechnoLabs Pvt Ltd
2024-04 To Current
- Developed Flutter applications.
## Flutter Developer
The Complete Softech Pvt Ltd
2021-10 To 2024-03
- Built mobile applications.
"""
    )
    assert resume["work_experience"][0]["job_title"] == "Sr. Flutter Developer"
    assert resume["work_experience"][0]["dates"] == "2024-04 To Current"
    assert resume["work_experience"][1]["job_title"] == "Flutter Developer"
    assert resume["work_experience"][1]["dates"] == "2021-10 To 2024-03"


def test_orphan_column_dates_recover_only_when_employment_pairing_is_unambiguous():
    resume = ResumeFieldExtractor.extract(
        """## Professional Experience
## Lead Developer
Alpha Systems Pvt Ltd
2022-01 To Current
## Developer
Beta Software Pvt Ltd
- Built production applications.
## Junior Developer
Gamma Technologies Pvt Ltd
- Maintained mobile applications.
## Education
Bachelor of Computer Applications
University Institute
## Candidate Name Lead Developer
2020-01 To 2021-12
2018-01 To 2019-12
2015-06 To 2018-05
## Skills
Flutter, Dart
"""
    )
    jobs = resume["work_experience"]
    assert [job["dates"] for job in jobs] == [
        "2022-01 To Current",
        "2020-01 To 2021-12",
        "2018-01 To 2019-12",
    ]
    assert jobs[1]["date_extraction_source"] == "orphan_range_document_order"
