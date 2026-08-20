#!/usr/bin/env python3
"""
Phase 0 CI Enforcement Gate: hardcoding_audit.py.

Verifies that no new unapproved P0/P1/P2 hardcoding findings are introduced.
Usage: python hardcoding_audit.py --baseline hardcoding-baseline.json --fail-on=new-unapproved
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:
    from .scan_repository_completeness import run_completeness_scan
except ImportError:  # Direct script execution.
    from scan_repository_completeness import run_completeness_scan


def finding_fingerprint(finding: dict) -> str:
    """Return a stable identity for one exact file/category/snippet occurrence."""
    normalized_snippet = re.sub(r"\s+", " ", str(finding.get("snippet", "")).strip())
    identity = "\0".join(
        (
            str(finding.get("file", "")),
            str(finding.get("category", "")),
            normalized_snippet,
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]


def load_approved_fingerprints(baseline_path: Path) -> set[str]:
    """Load only exact, owned, justified baseline identities."""
    approved: set[str] = set()
    if not baseline_path.exists():
        return approved
    baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
    for entry in baseline_data.get("allowlisted_findings", []):
        fingerprint = str(entry.get("fingerprint", "")).strip()
        if fingerprint and entry.get("owner") and entry.get("justification"):
            approved.add(fingerprint)
    return approved


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 0 Hardcoding CI Audit Runner")
    parser.add_argument("--baseline", type=str, default="hardcoding-baseline.json", help="Path to baseline allowlist JSON")
    parser.add_argument("--fail-on", type=str, default="new-unapproved", choices=["new-unapproved", "any"], help="Failure policy")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    baseline_path = repo_root / args.baseline

    # 1. Run fresh completeness scan
    scan_result = run_completeness_scan(repo_root, write_reports=False)
    active_findings = scan_result["findings"]["findings"]

    # 2. Load baseline allowlist
    try:
        approved_fingerprints = load_approved_fingerprints(baseline_path)
    except Exception as exc:
        print(f"❌ Failed to parse baseline file {baseline_path}: {exc}", file=sys.stderr)
        return 1

    new_unapproved: list[dict] = []
    for finding in active_findings:
        finding["fingerprint"] = finding_fingerprint(finding)
        is_approved = finding["fingerprint"] in approved_fingerprints
        if not is_approved:
            new_unapproved.append(finding)

    print("\n" + "=" * 70)
    print("🛡️  PHASE 0 HARDCODING AUDIT ENFORCEMENT SUMMARY")
    print("=" * 70)
    print(f"   - Total Tracked Files Scanned: {scan_result['coverage']['total_git_tracked_files']}")
    print(f"   - Total Active Findings:       {len(active_findings)}")
    print(f"   - Approved Baseline Identities:{len(approved_fingerprints):>7}")
    print(f"   - New Unapproved Findings:     {len(new_unapproved)}")

    if new_unapproved:
        print("\n❌ NEW UNAPPROVED HARDCODING FINDINGS DETECTED:")
        for f in new_unapproved:
            print(f"   • [{f['severity']}] {f['file']}:{f['line']} [{f['category']}] {f['snippet']}")
        print("\nFix the hardcoding or obtain approval + add owner & justification to hardcoding-baseline.json.")
        return 1

    print("\n✅ PHASE 0 REPOSITORY COMPLETENESS & HARDCODING AUDIT PASSED CLEANLY!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
