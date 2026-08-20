"""
Unit tests for Phase 3 Absolute Application Data Root & Path Governance.

Verifies:
1. APP_DATA_ROOT, UPLOADS_DIR, RESULTS_DIR, LOCK_DIR, TRAINING_DATA_DIR, OLLAMA_LOCK_FILE, and LLM_CONFIDENCE_CALIBRATION_PATH are absolute paths.
2. Dependent data paths inherit correctly from APP_DATA_ROOT.
3. No relative path initialization remains in runtime Settings.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings, settings


def test_app_data_root_paths_are_absolute():
    """Verify all runtime data paths in settings are absolute paths."""
    assert settings.APP_DATA_ROOT.is_absolute()
    assert settings.UPLOADS_DIR.is_absolute()
    assert settings.RESULTS_DIR.is_absolute()
    assert settings.LOCK_DIR.is_absolute()
    assert settings.TRAINING_DATA_DIR.is_absolute()
    assert settings.OLLAMA_LOCK_FILE.is_absolute()
    assert settings.LLM_CONFIDENCE_CALIBRATION_PATH.is_absolute()


def test_app_data_root_programmatic_override_derives_canonical_paths(tmp_path: Path):
    """Programmatic overrides must derive paths identically to environment configuration."""
    test_root = tmp_path / "var_lib_cv_analyzer"
    custom_settings = Settings(APP_DATA_ROOT=test_root)

    assert custom_settings.APP_DATA_ROOT == test_root.resolve()
    assert custom_settings.UPLOADS_DIR == test_root.resolve()
    assert custom_settings.RESULTS_DIR == (test_root / "results").resolve()
    assert custom_settings.LOCK_DIR == (test_root / ".locks").resolve()
    assert custom_settings.TRAINING_DATA_DIR == (test_root / "training_data").resolve()
    assert custom_settings.LEGACY_UPLOADS_DIR == (test_root / "uploads").resolve()
    assert custom_settings.LEGACY_RESULTS_DIR == (test_root / "uploads" / "results").resolve()


def test_explicit_dependent_path_overrides_are_preserved(tmp_path: Path):
    custom_uploads = tmp_path / "custom-uploads"
    custom_results = tmp_path / "custom-results"
    custom_settings = Settings(
        APP_DATA_ROOT=tmp_path / "data",
        UPLOADS_DIR=custom_uploads,
        RESULTS_DIR=custom_results,
    )

    assert custom_settings.UPLOADS_DIR == custom_uploads.resolve()
    assert custom_settings.RESULTS_DIR == custom_results.resolve()
