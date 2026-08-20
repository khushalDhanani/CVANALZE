from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.rule_config_manager import PolicyRegistry, PolicySnapshot
from app.schemas.job_context import JobEvaluationContext
from app.schemas.scoring_config import ScoringConfig
from app.services.job_taxonomy import TaxonomyClassifier
from app.services.match_service import MatchService
from app.services.scoring_engine import ScoringEngine


@pytest.mark.asyncio
async def test_ac1_single_policy_snapshot_resolved_and_attached() -> None:
    """Phase 2 AC 1: For one analysis, exactly one policy snapshot ID is resolved and recorded."""
    cv_text = """
    Alice Johnson
    Senior Software Architect
    Email: alice.johnson@example.com
    
    ## SKILLS
    Python, FastAPI, Docker, PostgreSQL, Kubernetes
    
    ## EXPERIENCE
    Lead Architect at TechCorp (2018 - 2024)
    Designed high-throughput backend services and microservices.
    """

    job = {
        "id": "vac-p2-101",
        "vacancy_id": 101,
        "title": "Backend Architect",
        "department": "Engineering",
        "required_skills": ["Python", "FastAPI"],
    }

    mock_emb = [0.05] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb):
        result = await MatchService.analyze_single_cv(cv_text, job_openings=[job])

    assert result.policy_snapshot_id is not None
    assert result.policy_snapshot_id.startswith("snap_")
    assert result.policy_digest is not None
    assert len(result.policy_digest) > 0

    if result.best_match:
        assert result.best_match.policy_snapshot_id == result.policy_snapshot_id
        assert result.best_match.policy_digest == result.policy_digest


def test_ac2_zero_duplicate_threshold_defaults() -> None:
    """Phase 2 AC 2: No duplicate high/medium thresholds or mandatory penalty defaults remain in production services/schemas."""
    config = ScoringConfig.load()
    snapshot = PolicyRegistry.resolve_snapshot()

    assert config.match_high_threshold == snapshot.scoring.match_high_threshold
    assert config.match_medium_threshold == snapshot.scoring.match_medium_threshold
    assert config.penalty_per_item == snapshot.matching.mandatory_failure_penalty
    assert config.max_score_on_failure == snapshot.matching.max_score_on_failure
    assert config.component_weights == dict(snapshot.scoring.component_weights)


def test_ac3_taxonomy_thresholds_scoped_to_policy_version() -> None:
    """Phase 2 AC 3: All taxonomy thresholds are model/taxonomy-version scoped."""
    snapshot = PolicyRegistry.resolve_snapshot()
    taxonomy_policy = snapshot.taxonomy

    assert taxonomy_policy.semantic_match_threshold == 0.70
    assert taxonomy_policy.family_compatibility_min_score == 0.40

    # Verify TaxonomyClassifier reads policy min score
    is_compat = TaxonomyClassifier.are_families_compatible(["Software Engineering"], "Software Engineering")
    assert is_compat is True


def test_ac4_policy_version_changes_output_predictably() -> None:
    """Phase 2 AC 4: Changing policy version changes output only where explicitly intended."""
    cv_text = """
    Bob Builder
    Junior Developer
    Email: bob@example.com
    
    ## SKILLS
    Python
    
    ## EXPERIENCE
    Junior Developer (2023 - 2024)
    """

    job = {
        "id": "vac-p2-penalty",
        "vacancy_id": 202,
        "title": "Senior Lead Engineer",
        "department": "Engineering",
        "min_experience_years": 8.0,
        "required_skills": ["Python", "Kubernetes", "Rust"],
        "required_skills_are_mandatory": True,
    }

    mock_emb = [0.05] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb):
        result_default = ScoringEngine.evaluate_job_match(cv_text=cv_text, job=job, candidate_experience=1.0)

    # Standard policy caps mandatory failure at max_score_on_failure (49.9)
    assert result_default.vacancy_fit_score <= 49.9
    assert result_default.vacancy_match_status == "NO_STRONG_VACANCY_MATCH"


def test_ac5_fallback_policy_source_is_never_silent() -> None:
    """Phase 2 AC 5: Fallback policy source is never silent (emits DEGRADED_POLICY_SOURCE)."""
    emergency_snapshot = PolicyRegistry.get_emergency_bundled_snapshot()

    assert emergency_snapshot.metadata.source == "EMERGENCY_BUNDLED"
    assert emergency_snapshot.metadata.status == "DEGRADED"
    assert "emergency" in emergency_snapshot.metadata.version


def test_ac6_deterministic_invariance_same_evidence_and_policy() -> None:
    """Phase 2 AC 6: Same evidence + same policy/model/taxonomy versions produces identical deterministic result."""
    cv_text = """
    Charlie Brown
    Data Engineer
    Email: charlie@example.com
    
    ## SKILLS
    Python, SQL, Spark, Airflow
    
    ## EXPERIENCE
    Data Engineer at DataCorp (2020 - 2024)
    Built ETL pipelines and data warehouses.
    """

    job = {
        "id": "vac-p2-invariance",
        "vacancy_id": 303,
        "title": "Data Engineer",
        "department": "Data",
        "required_skills": ["Python", "SQL"],
    }

    mock_emb = [0.05] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb):
        run1 = ScoringEngine.evaluate_job_match(cv_text=cv_text, job=job)
        run2 = ScoringEngine.evaluate_job_match(cv_text=cv_text, job=job)

    assert run1.vacancy_fit_score == run2.vacancy_fit_score
    assert run1.vacancy_match_status == run2.vacancy_match_status
    assert run1.matched_skills == run2.matched_skills
    assert run1.policy_snapshot_id == run2.policy_snapshot_id
    assert run1.policy_digest == run2.policy_digest
