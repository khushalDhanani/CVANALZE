"""
Unit tests for Phase 0 Repository Completeness Gate & Anti-Hardcoding Audit.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.quality.scan_repository_completeness import run_completeness_scan


def test_phase0_repository_completeness_coverage():
    """Verify that 100% of git-tracked files appear in coverage.json with a valid status."""
    repo_root = Path(__file__).resolve().parents[4]
    result = run_completeness_scan(repo_root)

    coverage = result["coverage"]
    assert coverage["total_git_tracked_files"] > 0
    assert len(coverage["files"]) == coverage["total_git_tracked_files"]

    valid_statuses = {"reviewed_clean", "findings", "binary_generated", "excluded_with_reason"}
    for rel_path, item in coverage["files"].items():
        assert item["status"] in valid_statuses, f"File {rel_path} has invalid status: {item['status']}"

    assert coverage["total_scanned_clean"] > 0


def test_phase0_baseline_file_integrity():
    """Verify hardcoding-baseline.json exists and all entries have required owner and justification."""
    repo_root = Path(__file__).resolve().parents[4]
    baseline_path = repo_root / "hardcoding-baseline.json"

    assert baseline_path.exists(), "hardcoding-baseline.json must exist at repo root"
    data = json.loads(baseline_path.read_text(encoding="utf-8"))

    assert "version" in data
    assert "owner" in data
    assert isinstance(data.get("allowlisted_findings"), list)

    for entry in data["allowlisted_findings"]:
        assert "file" in entry, "Baseline entry missing file"
        assert "category" in entry, "Baseline entry missing category"
        assert entry.get("owner"), f"Baseline entry for {entry['file']} missing owner"
        assert entry.get("justification"), f"Baseline entry for {entry['file']} missing justification"


def test_phase0_zero_unapproved_p0_secrets():
    """Verify zero unapproved P0 secrets exist across tracked files."""
    repo_root = Path(__file__).resolve().parents[4]
    result = run_completeness_scan(repo_root)

    p0_findings = [f for f in result["findings"]["findings"] if f["severity"] == "P0"]
    assert len(p0_findings) == 0, f"Found unapproved P0 secrets/credentials: {p0_findings}"
