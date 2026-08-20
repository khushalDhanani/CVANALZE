from __future__ import annotations

import tempfile
from pathlib import Path
from scripts.quality.check_no_hardcoding import scan_directory
from scripts.quality.check_frontend_hardcoding import scan_frontend_directory


def test_backend_scanner_catches_forbidden_candidate_fixtures() -> None:
    """Verifies that the backend AST scanner catches candidate fixture names and emails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        bad_file = tmp_path / "bad_service.py"
        bad_file.write_text("name = 'Johnathan Vance'\nemail = 'alex.mercer@example.com'\n", encoding="utf-8")

        violations = scan_directory(tmp_path)
        assert len(violations) >= 2
        assert any("johnathan vance" in v.lower() for v in violations)
        assert any("alex.mercer@example.com" in v.lower() for v in violations)


def test_backend_scanner_catches_production_placeholders() -> None:
    """Verifies that the backend AST scanner catches production placeholders."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        placeholder_file = tmp_path / "placeholder_service.py"
        placeholder_file.write_text("demand = 'mock_market_demand'\nrole = 'generic_candidate_role'\n", encoding="utf-8")

        violations = scan_directory(tmp_path)
        assert len(violations) >= 2
        assert any("mock_market_demand" in v.lower() for v in violations)


def test_backend_scanner_respects_policy_annotations() -> None:
    """Verifies that business decision thresholds with '# policy-approved-constant' do not trigger violations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        annotated_file = tmp_path / "annotated_service.py"
        annotated_file.write_text(
            "custom_threshold = 0.87  # policy-approved-constant\n",
            encoding="utf-8",
        )

        violations = scan_directory(tmp_path)
        assert len(violations) == 0


def test_frontend_scanner_catches_forbidden_placeholders() -> None:
    """Verifies that the frontend scanner catches forbidden placeholders in UI code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        bad_ui_file = tmp_path / "Component.tsx"
        bad_ui_file.write_text("const email = 'sarah.connor@example.com';\nconst mock = 'mock_market_demand';\n", encoding="utf-8")

        violations = scan_frontend_directory(tmp_path)
        assert len(violations) >= 2
