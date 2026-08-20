#!/usr/bin/env python3
"""
Phase 0 CI Enforcement Gate: hardcoding_audit.py.

Verifies that no new unapproved P0/P1/P2 hardcoding findings are introduced.
Usage: python hardcoding_audit.py --baseline hardcoding-baseline.json --fail-on=new-unapproved
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scan_repository_completeness import run_completeness_scan


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 0 Hardcoding CI Audit Runner")
    parser.add_argument("--baseline", type=str, default="hardcoding-baseline.json", help="Path to baseline allowlist JSON")
    parser.add_argument("--fail-on", type=str, default="new-unapproved", choices=["new-unapproved", "any"], help="Failure policy")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    baseline_path = repo_root / args.baseline

    # 1. Run fresh completeness scan
    scan_result = run_completeness_scan(repo_root)
    active_findings = scan_result["findings"]["findings"]

    # 2. Load baseline allowlist
    approved_keys: set[tuple[str, int, str]] = set()
    if baseline_path.exists():
        try:
            baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
            for entry in baseline_data.get("allowlisted_findings", []):
                # Verify owner and justification exist
                if not entry.get("owner") or not entry.get("justification"):
                    print(f"⚠️ Warning: Baseline entry for {entry.get('file')} missing owner or justification.", file=sys.stderr)
                file_path = entry.get("file", "")
                cat = entry.get("category", "")
                line = entry.get("line")
                if line is not None:
                    approved_keys.add((file_path, line, cat))
                else:
                    approved_keys.add((file_path, 0, cat))
                    approved_keys.add((file_path, cat))
        except Exception as exc:
            print(f"❌ Failed to parse baseline file {baseline_path}: {exc}", file=sys.stderr)

    new_unapproved: list[dict] = []
    for finding in active_findings:
        file_path = finding["file"]
        cat = finding["category"]
        line = finding["line"]
        is_approved = (file_path, line, cat) in approved_keys or (file_path, 0, cat) in approved_keys or (file_path, cat) in approved_keys
        if not is_approved:
            new_unapproved.append(finding)

    print("\n" + "=" * 70)
    print("🛡️  PHASE 0 HARDCODING AUDIT ENFORCEMENT SUMMARY")
    print("=" * 70)
    print(f"   - Total Tracked Files Scanned: {scan_result['coverage']['total_git_tracked_files']}")
    print(f"   - Total Active Findings:       {len(active_findings)}")
    print(f"   - Approved Baselined Findings: {len(approved_keys)}")
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
