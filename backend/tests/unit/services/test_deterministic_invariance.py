from __future__ import annotations

import copy
from typing import Any
from unittest.mock import patch

import pytest

from app.core.cache import CacheKey
from app.core.rule_config_manager import PolicyRegistry, RuleConfigManager
from app.schemas.match import JobMatchResult
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
from app.services.embedding_service import EmbeddingService
from app.services.experience_calculator import ExperienceCalculator, ExperienceState
from app.services.scoring_engine import ScoringEngine


@pytest.fixture
def sample_invariance_vacancy() -> dict[str, Any]:
    return {
        "id": "vac-inv-101",
        "vacancy_id": 101,
        "title": "Full Stack Python & React Developer",
        "department": "Engineering",
        "department_name": "Engineering",
        "department_id": 10,
        "main_department_id": 1,
        "min_experience_years": 4.0,
        "max_experience_years": 8.0,
        "required_skills": ["Python", "FastAPI", "React", "PostgreSQL"],
        "required_skills_are_mandatory": True,
        "preferred_keywords": ["Docker", "TypeScript", "Redis"],
        "job_description": "Full Stack Developer building robust web applications with Python, FastAPI, and React.",
        "responsibilities": "Develop backend endpoints, build user interface components, write unit tests.",
    }


@pytest.fixture
def sample_invariance_cv() -> str:
    return """
Liam Chen
Full Stack Developer
Email: liam.chen@example.com | Phone: +1 555-019-8833 | Location: San Jose, CA

## PROFESSIONAL SUMMARY
Full stack software engineer with 5 years of experience designing and shipping scalable web applications.
Specialized in Python FastAPI microservices, PostgreSQL databases, and modern React TypeScript frontends.

## SKILLS
- Programming: Python, TypeScript, JavaScript, SQL
- Web Technologies: FastAPI, React, Next.js, HTML5, CSS3
- Databases & Caching: PostgreSQL, Redis
- DevOps & Tooling: Docker, Git, GitHub Actions

## WORK EXPERIENCE
Software Engineer | Silicon Cloud Systems | February 2021 - Present
- Built and maintained REST APIs using Python and FastAPI with PostgreSQL.
- Implemented state management and UI features in React and TypeScript.
- Containerized services with Docker and improved CI build speeds.

Junior Web Developer | Apex Web Solutions | January 2019 - January 2021
- Created responsive web components using JavaScript, React, and CSS.
- Developed backend routes in Python Flask.

## EDUCATION
B.S. in Computer Science | San Jose State University | 2015 - 2019
"""


def test_scoring_engine_repeated_evaluation_invariance(
    sample_invariance_cv: str,
    sample_invariance_vacancy: dict[str, Any],
) -> None:
    """Release Gate 2.1: Asserts identical inputs + identical policy versions yield identical deterministic results."""
    mock_emb = [0.06] * 768
    results: list[JobMatchResult] = []

    with patch.object(EmbeddingService, "generate_embedding", return_value=mock_emb):
        for _ in range(5):
            res = ScoringEngine.evaluate_job_match(
                cv_text=sample_invariance_cv,
                job=copy.deepcopy(sample_invariance_vacancy),
                candidate_experience=5.0,
            )
            results.append(res)

    # Validate all 5 evaluations are byte-for-byte and float-for-float identical
    baseline = results[0]
    for idx, current in enumerate(results[1:], start=2):
        assert current.score == baseline.score, f"Score diverged on run {idx}"
        assert current.overall_score == baseline.overall_score
        assert current.vacancy_fit_score == baseline.vacancy_fit_score
        assert current.vacancy_match_status == baseline.vacancy_match_status
        assert current.classification == baseline.classification
        assert current.recommendation == baseline.recommendation
        assert current.role_score == baseline.role_score
        assert current.skills_score == baseline.skills_score
        assert current.experience_score == baseline.experience_score
        assert current.education_score == baseline.education_score
        assert current.domain_score == baseline.domain_score
        assert current.technology_score == baseline.technology_score
        assert current.responsibilities_score == baseline.responsibilities_score
        assert current.coverage == baseline.coverage
        assert current.matched_skills == baseline.matched_skills
        assert current.missing_skills == baseline.missing_skills
        assert len(current.mandatory_failures) == len(baseline.mandatory_failures)

        if baseline.score_breakdown and current.score_breakdown:
            assert current.score_breakdown.hierarchy_score == baseline.score_breakdown.hierarchy_score
            assert current.score_breakdown.designation_role_score == baseline.score_breakdown.designation_role_score
            assert current.score_breakdown.skills_score == baseline.score_breakdown.skills_score
            assert current.score_breakdown.experience_score == baseline.score_breakdown.experience_score
            assert current.score_breakdown.education_score == baseline.score_breakdown.education_score
            assert current.score_breakdown.semantic_similarity_score == baseline.score_breakdown.semantic_similarity_score
            assert current.score_breakdown.overall_fit_score == baseline.score_breakdown.overall_fit_score


def test_policy_registry_digest_invariance() -> None:
    """Release Gate 2.2: PolicyRegistry digest is stable and reproducible across calls."""
    digest_1 = PolicyRegistry.get_policy_digest()
    digest_2 = PolicyRegistry.get_policy_digest()
    digest_3 = RuleConfigManager.get_policy_digest()

    assert len(digest_1) == 16
    assert digest_1 == digest_2
    assert digest_2 == digest_3


def test_policy_registry_digest_changes_on_rule_modification() -> None:
    """Release Gate 2.3: Policy digest changes whenever configuration parameters are altered."""
    base_config = RuleConfigManager.get_config()
    base_digest = RuleConfigManager.compute_policy_digest(base_config)

    # Mutate a scoring threshold in a copy
    mutated = base_config.model_copy(deep=True)
    mutated.scoring.match.scoring_parameters.match_high_threshold = 85.0
    mutated_digest = RuleConfigManager.compute_policy_digest(mutated)

    assert base_digest != mutated_digest, "Policy digest must change when a threshold is modified"


def test_taxonomy_classification_invariance() -> None:
    """Release Gate 2.4: Dynamic taxonomy classification is deterministic for identical candidate roles/skills."""
    role = "Senior Cloud DevOps Engineer"
    skills = ["Docker", "Kubernetes", "AWS", "Terraform", "CI/CD"]
    mock_emb = [0.05] * 768

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb):
        results = [
            DynamicTaxonomyService.resolve_candidate_role_and_domain(role_or_summary=role, skills=skills)
            for _ in range(5)
        ]

    base = results[0]
    for current in results[1:]:
        assert current.industry_domain == base.industry_domain
        assert current.industry_department == base.industry_department
        assert current.confidence == base.confidence


def test_experience_calculator_invariance() -> None:
    """Release Gate 2.5: Experience calculation and interval merging is strictly deterministic."""
    resume_json = {
        "work_experience": [
            {"job_title": "Developer A", "company": "Company A", "dates": "Jan 2020 - Jan 2022"},
            {"job_title": "Developer B", "company": "Company B", "dates": "Jan 2021 - Jan 2023"},
        ]
    }

    results = [
        ExperienceCalculator.calculate_canonical_experience(resume_json)
        for _ in range(5)
    ]

    base = results[0]
    for current in results[1:]:
        assert current["experience_state"] == ExperienceState.CALCULATED
        assert current["total_experience_years"] == base["total_experience_years"]
        assert current["merged_intervals_count"] == base["merged_intervals_count"]


def test_match_cache_key_invariance() -> None:
    """Release Gate 2.6: CacheKey incorporates policy version digest and generates identical keys for identical inputs."""
    policy_digest = PolicyRegistry.get_policy_digest()

    ck1 = CacheKey.for_match_result(
        document_hash="test_hash_invariance_123",
        candidate_id="cand_123",
        vacancy_version="v1",
        vacancy_ids=["vac-1", "vac-2"],
        prompt_version="p1",
        model_version="m1",
        extraction_version="e1",
        matching_version="m1",
        rule_version=f"1.0.0:{policy_digest}",
        taxonomy_version="t1",
    )
    key_1 = ck1.to_key()

    ck2 = CacheKey.for_match_result(
        document_hash="test_hash_invariance_123",
        candidate_id="cand_123",
        vacancy_version="v1",
        vacancy_ids=["vac-1", "vac-2"],
        prompt_version="p1",
        model_version="m1",
        extraction_version="e1",
        matching_version="m1",
        rule_version=f"1.0.0:{policy_digest}",
        taxonomy_version="t1",
    )
    key_2 = ck2.to_key()

    assert key_1 == key_2
    assert policy_digest in ck1.components.get("rule_ver", "")
