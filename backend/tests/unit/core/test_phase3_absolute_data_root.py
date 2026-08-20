"""
Unit tests for Phase 3 Absolute Application Data Root & Path Governance.

Verifies:
1. APP_DATA_ROOT, UPLOADS_DIR, RESULTS_DIR, LOCK_DIR, TRAINING_DATA_DIR, OLLAMA_LOCK_FILE, and LLM_CONFIDENCE_CALIBRATION_PATH are absolute paths.
2. Dependent data paths inherit correctly from APP_DATA_ROOT.
3. No relative path initialization remains in runtime Settings.
"""

from __future__ import annotations

import os
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


def test_app_data_root_environment_override(tmp_path: Path):
    """Verify setting APP_DATA_ROOT via env var dynamically updates derived paths."""
    test_root = tmp_path / "var_lib_cv_analyzer"
    test_root.mkdir(parents=True, exist_ok=True)

    original_env = os.environ.get("APP_DATA_ROOT")
    try:
        os.environ["APP_DATA_ROOT"] = str(test_root)
        custom_settings = Settings()

        assert custom_settings.APP_DATA_ROOT == test_root.resolve()
        assert str(custom_settings.UPLOADS_DIR).startswith(str(test_root.resolve()))
        assert str(custom_settings.RESULTS_DIR).startswith(str(test_root.resolve()))
        assert str(custom_settings.LOCK_DIR).startswith(str(test_root.resolve()))
        assert str(custom_settings.TRAINING_DATA_DIR).startswith(str(test_root.resolve()))
    finally:
        if original_env is not None:
            os.environ["APP_DATA_ROOT"] = original_env
        else:
            os.environ.pop("APP_DATA_ROOT", None)
