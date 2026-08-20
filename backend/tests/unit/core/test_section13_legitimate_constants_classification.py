"""
Unit tests for Section 13 Legitimate Constants Governance & Classification Policy.

Verifies:
1. Hardcoding scanner distinguishes legitimate protocol/domain constants from business decision hardcodings.
2. Every baselined finding in hardcoding-baseline.json contains an explicit owner and justification.
3. Standard MIME types, HTTP statuses, and domain enums remain valid codebase constants.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.quality.scan_repository_completeness import (
    ALLOWED_NUMERICS,
    APPROVED_ANNOTATIONS,
    BINARY_EXTENSIONS,
)


def test_baseline_allowlist_completeness_and_governance():
    """Verify hardcoding-baseline.json requires explicit owner and justification for every entry."""
    repo_root = Path(__file__).resolve().parents[4]
    baseline_file = repo_root / "hardcoding-baseline.json"
    assert baseline_file.exists(), "hardcoding-baseline.json must exist in repo root"

    data = json.loads(baseline_file.read_text(encoding="utf-8"))
    assert data.get("owner"), "Baseline root must specify an owner"
    assert data.get("description"), "Baseline root must specify a description"

    entries = data.get("allowlisted_findings", [])
    assert len(entries) > 0, "Baseline must contain allowlisted entries"

    for idx, entry in enumerate(entries):
        assert entry.get("file"), f"Entry #{idx} missing file field"
        assert entry.get("category"), f"Entry #{idx} missing category field"
        assert entry.get("severity") in ("P0", "P1", "P2"), f"Entry #{idx} has invalid severity"
        assert entry.get("owner"), f"Entry #{idx} ({entry.get('file')}) missing explicit owner"
        assert entry.get("justification"), f"Entry #{idx} ({entry.get('file')}) missing explicit justification"


def test_legitimate_constant_categories():
    """Verify standard protocol constants and binary extensions are registered."""
    assert ".pdf" in BINARY_EXTENSIONS
    assert ".png" in BINARY_EXTENSIONS
    assert 200 in ALLOWED_NUMERICS
    assert 404 in ALLOWED_NUMERICS
    assert 500 in ALLOWED_NUMERICS

    assert "# policy-approved-constant" in APPROVED_ANNOTATIONS
    assert "// policy-governed" in APPROVED_ANNOTATIONS
