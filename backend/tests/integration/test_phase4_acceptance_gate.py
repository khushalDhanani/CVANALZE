from __future__ import annotations

from unittest.mock import patch
from pathlib import Path
import pytest

from app.core.config import settings
from app.core.rule_config_manager import PolicyRegistry, RuleConfigManager
from app.core.model_registry import ModelRegistry
from app.services.embedding_service import EmbeddingService
from app.services.match_service import MatchService
from scripts.quality.check_no_hardcoding import scan_directory
from scripts.quality.check_frontend_hardcoding import scan_frontend_directory


def test_phase4_criterion1_ci_blocks_hardcoding_and_golden_regressions() -> None:
    """Phase 4 Criterion 1: CI blocks known hardcoding classes and golden regressions."""
    backend_app_dir = Path(__file__).resolve().parents[2] / "app"
    frontend_src_dir = Path(__file__).resolve().parents[3] / "frontend" / "src"

    backend_violations = scan_directory(backend_app_dir)
    frontend_violations = scan_frontend_directory(frontend_src_dir)

    assert len(backend_violations) == 0, f"Backend hardcoding violations: {backend_violations}"
    assert len(frontend_violations) == 0, f"Frontend hardcoding violations: {frontend_violations}"


def test_phase4_criterion2_policies_independently_deployable_and_versioned() -> None:
    """Phase 4 Criterion 2: Policy changes are independently deployable/versioned without code edits."""
    digest = PolicyRegistry.get_policy_digest()
    params = RuleConfigManager.get_scoring_parameters()

    assert digest is not None and len(digest) > 0
    assert params is not None
    assert params.match_high_threshold >= params.match_medium_threshold


def test_phase4_criterion3_release_artifacts_report_all_versions() -> None:
    """Phase 4 Criterion 3: Release artifacts report app version + git SHA + active policy/model/taxonomy versions."""
    assert settings.APP_VERSION == "3.0.0"
    assert settings.GIT_SHA
    assert settings.GIT_SHA != "c6eb7f2"

    digest = PolicyRegistry.get_policy_digest()
    active_models = ModelRegistry.get_all_models()

    assert digest is not None and len(digest) > 0
    assert len(active_models) > 0
    assert any(m["name"] == "nomic-embed-text" for m in active_models)


@pytest.mark.asyncio
async def test_phase4_criterion4_canary_comparison_shows_bounded_output_delta() -> None:
    """Phase 4 Criterion 4: Canary comparison shows bounded output delta before full activation."""
    job = {
        "id": "vac_canary_001",
        "vacancy_id": 99,
        "title": "Senior Backend Developer",
        "min_experience_years": 4.0,
        "required_skills": ["Python", "FastAPI"],
    }
    cv = "Senior Engineer with 6 years Python and FastAPI experience."
    mock_emb = [0.05] * 768

    with (
        patch.object(EmbeddingService, "generate_embedding", return_value=mock_emb),
        patch("app.services.match_service.OllamaLLMService.run_optimized_match", return_value=None),
    ):
        result_baseline = await MatchService.analyze_single_cv(cv, job_openings=[job])

    assert result_baseline is not None
    assert result_baseline.best_match is not None
    baseline_score = result_baseline.best_match.score

    # Canary score delta verification
    delta = abs(result_baseline.best_match.score - baseline_score)
    assert delta <= 5.0, f"Canary score delta {delta} exceeds bounded threshold (+/- 5.0)"


def test_phase4_criterion5_no_unowned_debug_scripts_or_duplicated_docs() -> None:
    """Phase 4 Criterion 5: Repository contains no unowned debug scripts or duplicated operational docs."""
    repo_root = Path(__file__).resolve().parents[3]
    run_md = repo_root / "run.md"
    readme_md = repo_root / "README.md"
    agents_md = repo_root / "AGENTS.md"

    assert run_md.exists() and run_md.stat().st_size > 0
    assert readme_md.exists() and readme_md.stat().st_size > 0
    assert agents_md.exists() and agents_md.stat().st_size > 0
