from __future__ import annotations

import json
from pathlib import Path
import tomllib

from app.core.config import Settings, settings


def test_app_version_and_git_sha_exposed() -> None:
    """The compatibility version alias must use the canonical app version."""
    assert settings.APP_VERSION == "3.0.0"
    assert settings.VERSION == settings.APP_VERSION
    assert settings.GIT_SHA != "c6eb7f2"


def test_development_git_sha_uses_explicit_unknown_value() -> None:
    configured = Settings(APP_ENVIRONMENT="development", APP_VERSION="4.2.1", GIT_SHA="")

    assert configured.VERSION == "4.2.1"
    assert configured.GIT_SHA == "unknown"


def test_pyproject_toml_version_aligned() -> None:
    """Verifies that pyproject.toml version matches 3.0.0."""
    pyproject_path = Path(__file__).resolve().parents[3] / "pyproject.toml"
    assert pyproject_path.exists()

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    assert data["project"]["version"] == "3.0.0"


def test_frontend_package_json_version_aligned() -> None:
    """Verifies that frontend package.json version matches 3.0.0."""
    package_path = Path(__file__).resolve().parents[4] / "frontend" / "package.json"
    assert package_path.exists()

    data = json.loads(package_path.read_text(encoding="utf-8"))
    assert data["version"] == "3.0.0"


def test_operational_documentation_single_source_of_truth() -> None:
    """Verifies that operational run.md and AGENTS.md exist at repository root."""
    repo_root = Path(__file__).resolve().parents[4]
    run_md = repo_root / "run.md"
    readme_md = repo_root / "README.md"
    agents_md = repo_root / "AGENTS.md"

    assert run_md.exists() and run_md.stat().st_size > 0
    assert readme_md.exists() and readme_md.stat().st_size > 0
    assert agents_md.exists() and agents_md.stat().st_size > 0
