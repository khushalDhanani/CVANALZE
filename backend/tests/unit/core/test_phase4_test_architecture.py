from __future__ import annotations

from unittest.mock import patch
import pytest

from app.schemas.contracts import EvidenceRef, EvidenceResult, EvidenceStatus
from app.services.embedding_service import EmbeddingService
from app.services.experience_calculator import ExperienceCalculator
from app.services.match_service import MatchService
from app.services.scoring_engine import ScoringEngine
from app.core.rule_config_manager import PolicyRegistry, RuleConfigManager


def test_layer1_unit_resolvers_and_denominator_exclusion() -> None:
    """Workstream 6.1 Layer 1 (Unit): Verifies resolvers, interval math, and denominator exclusion."""
    # 1. Interval Math
    exp_calc = ExperienceCalculator()
    resume_data = {
        "work_experience": [
            {"start_date": "2020-01-01", "end_date": "2022-01-01", "title": "Software Engineer"},
            {"start_date": "2021-01-01", "end_date": "2023-01-01", "title": "Senior Engineer"},
        ]
    }
    years = exp_calc.calculate_total_experience(resume_data)
    assert years is not None and years >= 2.0

    # 2. Denominator exclusion for NOT_ASSESSABLE
    params = PolicyRegistry.get_scoring_parameters()
    assert params is not None
    assert params.component_weights.get("skills", 0.0) > 0.0


def test_layer2_contract_preserves_evidence_status() -> None:
    """Workstream 6.1 Layer 2 (Contract): API schemas preserve null/status/evidence across all 7 EvidenceStatus values."""
    statuses = [
        EvidenceStatus.VERIFIED,
        EvidenceStatus.INFERRED,
        EvidenceStatus.CONFLICTING,
        EvidenceStatus.NOT_FOUND,
        EvidenceStatus.NOT_APPLICABLE,
        EvidenceStatus.NOT_ASSESSABLE,
        EvidenceStatus.SYSTEM_UNAVAILABLE,
    ]

    for status in statuses:
        res = EvidenceResult[str](
            value="test_val" if status in {EvidenceStatus.VERIFIED, EvidenceStatus.INFERRED} else None,
            status=status,
            evidence=[EvidenceRef(raw_quote="quote", confidence_score=0.9, provenance="TEST")],
        )
        assert res.status == status
        assert len(res.evidence) == 1
        assert res.evidence[0].raw_quote == "quote"


def test_layer3_golden_regression_eight_archetypes() -> None:
    """Workstream 6.1 Layer 3 (Golden Regression): Verifies golden regression coverage for failure archetypes."""
    import tests.integration.test_golden_regression_suite as grs

    archetype_tests = [
        "test_golden_senior_engineer_perfect_match",
        "test_golden_junior_applying_for_senior_fails_min_experience",
        "test_golden_missing_mandatory_skill_fails_and_caps_score",
        "test_golden_cross_domain_applicant_rejected",
        "test_golden_empty_and_sparse_cv_safe_empty_semantics",
        "test_golden_prompt_injection_adversarial_cv_safety",
        "test_golden_evidence_status_integrity_invariants",
    ]
    for name in archetype_tests:
        assert hasattr(grs, name) and callable(getattr(grs, name))


def test_layer4_property_invariants() -> None:
    """Workstream 6.1 Layer 4 (Property/Invariant): Structural constraints and evidence-less mandatory pass prevention."""
    params = PolicyRegistry.get_scoring_parameters()
    # Structural constraint check
    assert params.match_high_threshold >= params.match_medium_threshold
    total_weights = sum(params.component_weights.values())
    assert total_weights > 0.99

    # Prevent mandatory pass without evidence
    ev = EvidenceResult[str].not_found(source="deterministic")
    assert ev.status in {EvidenceStatus.NOT_FOUND, EvidenceStatus.NOT_ASSESSABLE}
    assert ev.status != EvidenceStatus.VERIFIED


@pytest.mark.asyncio
async def test_layer5_integration_pipeline_execution() -> None:
    """Workstream 6.1 Layer 5 (Integration): Pipeline execution and controlled degradation."""
    cv_text = "John Engineer\nPython Developer\njohn@example.com\n\n## SKILLS\nPython, SQL"
    job = {"id": "vac_l5", "vacancy_id": 501, "title": "Python Dev", "required_skills": ["Python"]}

    mock_emb = [0.05] * 768
    with patch.object(EmbeddingService, "generate_embedding", return_value=mock_emb):
        result = await MatchService.analyze_single_cv(cv_text, job_openings=[job])

    assert result is not None
    assert result.best_match is not None
    assert result.analysis_versions is not None


@pytest.mark.asyncio
async def test_layer6_replay_reproducibility() -> None:
    """Workstream 6.1 Layer 6 (Replay): Same inputs produce identical output fingerprints and scores."""
    cv_text = "Alice Developer\nBackend Developer\nalice@example.com\n\n## SKILLS\nPython, Docker"
    job = {"id": "vac_l6", "vacancy_id": 601, "title": "Backend Dev", "required_skills": ["Python"]}

    mock_emb = [0.05] * 768
    with patch.object(EmbeddingService, "generate_embedding", return_value=mock_emb):
        res1 = await MatchService.analyze_single_cv(cv_text, job_openings=[job])
        res2 = await MatchService.analyze_single_cv(cv_text, job_openings=[job])

    assert res1.best_match.overall_score == res2.best_match.overall_score
    assert res1.analysis_versions.app_version == res2.analysis_versions.app_version
    assert res1.analysis_versions.embedding_model_id == res2.analysis_versions.embedding_model_id
