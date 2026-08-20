from __future__ import annotations

from inspect import getsource
from types import SimpleNamespace
from unittest.mock import patch

from app.core.rule_config_manager import PolicyRegistry
from app.schemas.match import JobMatchResult
from app.schemas.scoring_config import ScoringConfig
from app.services.match_evaluators import ComponentScoreEvaluator
from app.services.scoring_engine import ScoringEngine


def test_scoring_config_loads_from_policy_snapshot() -> None:
    """Workstream 4.2: ScoringConfig loads parameters directly from PolicyRegistry snapshot."""
    config = ScoringConfig.load()
    snapshot = PolicyRegistry.resolve_snapshot()

    assert config.profile_version == snapshot.metadata.version
    assert config.profile_code in ("DATABASE", "EMERGENCY_BUNDLED")
    assert config.penalty_per_item == snapshot.matching.mandatory_failure_penalty
    assert config.max_score_on_failure == snapshot.matching.max_score_on_failure
    assert config.component_weights == dict(snapshot.scoring.component_weights)


def test_scoring_config_preserves_policy_caps() -> None:
    snapshot = SimpleNamespace(
        metadata=SimpleNamespace(source="DATABASE", version="tenant-v3"),
        matching=SimpleNamespace(mandatory_failure_penalty=22.0, max_score_on_failure=48.0),
        scoring=SimpleNamespace(
            llm_semantic_weight=0.12,
            max_llm_boost=9.0,
            match_high_threshold=77.0,
            match_medium_threshold=48.0,
            zero_skills_score_cap=17.0,
            rejection_score_epsilon=0.25,
            component_weights={"skills": 1.0},
        ),
    )

    with patch("app.core.rule_config_manager.PolicyRegistry.resolve_snapshot", return_value=snapshot):
        config = ScoringConfig.load(tenant_id="tenant-a")

    assert config.zero_skills_score_cap == 17.0
    assert config.rejection_score_epsilon == 0.25


def test_component_scoring_has_no_literal_zero_skills_fallback() -> None:
    source = getsource(ComponentScoreEvaluator.evaluate)

    assert 'getattr(params, "zero_skills_score_cap", 40.0)' not in source


def test_formula_excludes_not_assessable_components() -> None:
    """Workstream 4.2: Un-evaluable components (None) are excluded from active weight denominator."""
    cv_text = """
    Jane Doe
    Software Engineer
    Email: jane.doe@example.com
    
    ## SKILLS
    Python, FastAPI, Docker, PostgreSQL
    
    ## EXPERIENCE
    Software Engineer at CloudCorp (2020 - 2024)
    Built backend microservices and databases.
    """
    job = {
        "id": "vac-unified-101",
        "vacancy_id": 101,
        "title": "Python Developer",
        "department": "Engineering",
        "required_skills": ["Python", "FastAPI"],
        # No education requirement specified -> education_score = None (NOT_ASSESSABLE)
    }

    mock_emb = [0.05] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb):
        result = ScoringEngine.evaluate_job_match(cv_text=cv_text, job=job)

    assert isinstance(result, JobMatchResult)
    assert result.scoring_policy_version is not None
    assert result.component_assessability["education"] == "NOT_ASSESSABLE"
    assert result.component_assessability["skills"] == "VERIFIED"
    assert result.vacancy_fit_score > 0.0


def test_mandatory_failure_capping_and_facts() -> None:
    """Workstream 4.2: Mandatory requirement failures cap final fit score and emit structured facts."""
    cv_text = """
    John Smith
    Junior Developer
    Email: john@example.com
    
    ## SKILLS
    Python
    
    ## EXPERIENCE
    Software Intern (Jan 2024 - Mar 2024)
    """
    job = {
        "id": "vac-senior-req",
        "vacancy_id": 202,
        "title": "Senior Staff Architect",
        "department": "Engineering",
        "min_experience_years": 8.0,
        "required_skills": ["Python", "Kubernetes", "Rust", "System Architecture"],
        "required_skills_are_mandatory": True,
    }

    mock_emb = [0.05] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb):
        result = ScoringEngine.evaluate_job_match(cv_text=cv_text, job=job, candidate_experience=0.2)

    assert len(result.mandatory_failures) > 0
    assert result.vacancy_fit_score <= 49.9
    assert result.vacancy_match_status == "NO_STRONG_VACANCY_MATCH"
    assert result.mandatory_failures[0].failure_code != ""
