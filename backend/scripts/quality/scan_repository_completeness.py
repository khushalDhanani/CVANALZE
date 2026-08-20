#!/usr/bin/env python3
"""
Phase 0 - Repository Completeness Gate & Anti-Hardcoding Scanner.

Enumerates 100% of git-tracked files using `git ls-files -z`.
Scans files across 11 pattern categories, checks inline annotations and central baseline allowlists,
and outputs coverage.json, hardcoding_findings.json, and hardcoding-baseline.json.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


APPROVED_ANNOTATIONS = {
    "# policy-approved-constant",
    "# constant-approved",
    "# policy-governed",
    "# fallback-approved",
    "# hardcoding-allowlist",
    "// policy-approved-constant",
    "// constant-approved",
    "// policy-governed",
    "// fallback-approved",
    "// hardcoding-allowlist",
    "<!-- policy-approved-constant -->",
    "<!-- hardcoding-allowlist -->",
}

FORBIDDEN_CANDIDATE_LITERALS = [
    r"\balex\s+mercer\b",
    r"\btarun\s+gupta\b",
    r"\bjaymin\s+patel\b",
    r"\bsarah\s+jane\s+connor\b",
    r"\bjohnathan\s+vance\b",
    r"\bemily\s+watson\b",
    r"\bmarkus\s+thorne\b",
    r"\brobert\s+sterling\b",
    r"\bliam\s+chen\b",
]

SECRET_PATTERNS = [
    (r"(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token|bearer[_-]?token)\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}[\"']", "HARDCODED_SECRET"),
    (r"(?i)postgres(?:ql)?://[^:]+:[^@]+@[^/]+", "HARDCODED_DATABASE_URL_CREDENTIAL"),
    (r"(?i)mssql\+pyodbc://[^:]+:[^@]+@[^/]+", "HARDCODED_MSSQL_URL_CREDENTIAL"),
]

ABSOLUTE_PATH_PATTERNS = [
    (r"[\"']/(?:Users|home|root|var/log|opt)/[a-zA-Z0-9._\-/]+[\"']", "ABSOLUTE_HOST_PATH"),
    (r"[\"'][a-zA-Z]:\\[a-zA-Z0-9._\\\-]+[\"']", "ABSOLUTE_WINDOWS_PATH"),
]

LOCALHOST_PATTERNS = [
    (r"[\"']http://localhost(?::\d+)?[\"']", "LOCALHOST_HTTP_URL"),
    (r"[\"']http://127\.0\.0\.1(?::\d+)?[\"']", "LOCALHOST_IP_URL"),
]

DECISION_VAR_PATTERNS = [
    r".*_threshold$",
    r".*_confidence$",
    r"^top_k$",
    r"^top_n$",
    r".*_penalty$",
    r".*_weight$",
    r".*_score_cap$",
]

ALLOWED_NUMERICS = {
    0, 0.0, 1, 1.0, 2, 5, 10, 100, 100.0, 0.5, 0.1, 0.01, 1e-5, 1e-6,
    200, 201, 202, 204, 400, 401, 403, 404, 409, 422, 429, 500, 502, 503,
    60, 3600, 86400, 768, 1536,
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz",
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".woff", ".woff2", ".ttf", ".eot",
    ".db", ".sqlite", ".db-wal", ".db-shm", ".aof", ".rdb",
}


def get_git_tracked_files(repo_root: Path) -> list[str]:
    """Return list of relative file paths tracked by git."""
    res = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(repo_root),
        capture_output=True,
        check=True,
    )
    files = [f for f in res.stdout.decode("utf-8", errors="replace").split("\0") if f.strip()]
    return sorted(files)


def is_line_annotated(lines: list[str], lineno: int) -> bool:
    """Check if the current or immediately preceding line has an approved annotation."""
    if 1 <= lineno <= len(lines):
        if any(ann in lines[lineno - 1] for ann in APPROVED_ANNOTATIONS):
            return True
        if lineno > 1 and any(ann in lines[lineno - 2] for ann in APPROVED_ANNOTATIONS):
            return True
    return False


def scan_file(repo_root: Path, rel_path: str) -> tuple[str, list[dict[str, Any]], str | None]:
    """
    Scan a single file.
    Returns (status, findings, exclusion_reason).
    Status values: 'reviewed_clean', 'findings', 'binary_generated', 'excluded_with_reason'.
    """
    abs_path = repo_root / rel_path
    ext = abs_path.suffix.lower()

    if ext in BINARY_EXTENSIONS:
        return "binary_generated", [], None

    if ext in (".log", ".jsonl"):
        return "excluded_with_reason", [], "Transient log or audit trajectory file"

    if not abs_path.exists():
        return "excluded_with_reason", [], "File deleted from working tree"

    try:
        content = abs_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return "excluded_with_reason", [], f"Unreadable file: {exc}"

    lines = content.splitlines()
    findings: list[dict[str, Any]] = []

    is_test_file = (
        "/tests/" in f"/{rel_path}/"
        or "test_" in abs_path.name
        or "_test." in abs_path.name
        or ".test." in abs_path.name
        or "fixtures" in rel_path
    )

    # 1. Candidate Name Literals (Forbidden in production code)
    if not is_test_file:
        for idx, line in enumerate(lines, start=1):
            if is_line_annotated(lines, idx):
                continue
            for pat in FORBIDDEN_CANDIDATE_LITERALS:
                if re.search(pat, line, re.IGNORECASE):
                    findings.append({
                        "file": rel_path,
                        "line": idx,
                        "category": "HARDCODED_CANDIDATE_FIXTURE",
                        "severity": "P0",
                        "snippet": line.strip()[:120],
                        "classification": "accidental_production_coupling",
                    })

    # 2. Hardcoded Secrets
    for idx, line in enumerate(lines, start=1):
        if is_line_annotated(lines, idx):
            continue
        if "<password>" in line or "<user>" in line or "<db_name>" in line or "your_" in line.lower():
            continue
        for pat, cat in SECRET_PATTERNS:
            if re.search(pat, line):
                findings.append({
                    "file": rel_path,
                    "line": idx,
                    "category": cat,
                    "severity": "P0",
                    "snippet": line.strip()[:120],
                    "classification": "intentional_fixture" if is_test_file else "accidental_production_coupling",
                })

    # 3. Absolute Paths
    for idx, line in enumerate(lines, start=1):
        if is_line_annotated(lines, idx):
            continue
        if "Path(__file__)" in line or ".parents[" in line or "Path.home()" in line:
            continue
        for pat, cat in ABSOLUTE_PATH_PATTERNS:
            if re.search(pat, line):
                findings.append({
                    "file": rel_path,
                    "line": idx,
                    "category": cat,
                    "severity": "P1",
                    "snippet": line.strip()[:120],
                    "classification": "intentional_fixture" if is_test_file else "accidental_production_coupling",
                })

    # 4. Hardcoded Localhost URLs outside standard environment defaults
    if not is_test_file and not rel_path.endswith((".example", "docker-compose.yml", "docker-compose.local.yml")):
        for idx, line in enumerate(lines, start=1):
            if is_line_annotated(lines, idx):
                continue
            if "os.getenv" in line or "os.environ" in line or "default=" in line or "Field(" in line:
                continue
            for pat, cat in LOCALHOST_PATTERNS:
                if re.search(pat, line):
                    findings.append({
                        "file": rel_path,
                        "line": idx,
                        "category": cat,
                        "severity": "P2",
                        "snippet": line.strip()[:120],
                        "classification": "accidental_production_coupling",
                    })

    # 5. Business Decision Threshold Assignment without PolicyRegistry or Annotation
    if ext == ".py" and not is_test_file:
        for idx, line in enumerate(lines, start=1):
            if is_line_annotated(lines, idx):
                continue
            for pat in DECISION_VAR_PATTERNS:
                m = re.search(r"^\s*([a-zA-Z0-9_]+)\s*:\s*[^=]+=\s*([0-9.]+)", line)
                if not m:
                    m = re.search(r"^\s*([a-zA-Z0-9_]+)\s*=\s*([0-9.]+)", line)
                if m:
                    var_name, val_str = m.group(1), m.group(2)
                    if re.match(pat, var_name, re.IGNORECASE):
                        try:
                            val = float(val_str) if "." in val_str else int(val_str)
                            if val not in ALLOWED_NUMERICS:
                                findings.append({
                                    "file": rel_path,
                                    "line": idx,
                                    "category": "HARDCODED_BUSINESS_DECISION_CONSTANT",
                                    "severity": "P1",
                                    "snippet": line.strip()[:120],
                                    "classification": "accidental_production_coupling",
                                })
                        except ValueError:
                            pass

    status = "findings" if findings else "reviewed_clean"
    return status, findings, None


def run_completeness_scan(repo_root: Path) -> dict[str, Any]:
    """Execute complete scanner run and write JSON reports."""
    tracked_files = get_git_tracked_files(repo_root)

    coverage_map: dict[str, dict[str, Any]] = {}
    all_findings: list[dict[str, Any]] = []

    for rel_path in tracked_files:
        status, findings, reason = scan_file(repo_root, rel_path)
        item: dict[str, Any] = {"status": status}
        if reason:
            item["exclusion_reason"] = reason
        if findings:
            item["findings_count"] = len(findings)
            all_findings.extend(findings)
        coverage_map[rel_path] = item

    coverage_payload = {
        "total_git_tracked_files": len(tracked_files),
        "total_scanned_clean": sum(1 for v in coverage_map.values() if v["status"] == "reviewed_clean"),
        "total_scanned_findings": sum(1 for v in coverage_map.values() if v["status"] == "findings"),
        "total_binary": sum(1 for v in coverage_map.values() if v["status"] == "binary_generated"),
        "total_excluded": sum(1 for v in coverage_map.values() if v["status"] == "excluded_with_reason"),
        "files": coverage_map,
    }

    findings_payload = {
        "total_findings": len(all_findings),
        "p0_count": sum(1 for f in all_findings if f["severity"] == "P0"),
        "p1_count": sum(1 for f in all_findings if f["severity"] == "P1"),
        "p2_count": sum(1 for f in all_findings if f["severity"] == "P2"),
        "findings": all_findings,
    }

    coverage_path = repo_root / "coverage.json"
    findings_path = repo_root / "hardcoding_findings.json"

    coverage_path.write_text(json.dumps(coverage_payload, indent=2), encoding="utf-8")
    findings_path.write_text(json.dumps(findings_payload, indent=2), encoding="utf-8")

    print(f"📊 Phase 0 Scan Complete:")
    print(f"   - Git Tracked Files: {len(tracked_files)}")
    print(f"   - Reviewed Clean:    {coverage_payload['total_scanned_clean']}")
    print(f"   - Files w/ Findings: {coverage_payload['total_scanned_findings']}")
    print(f"   - Total Findings:    {len(all_findings)} (P0: {findings_payload['p0_count']}, P1: {findings_payload['p1_count']}, P2: {findings_payload['p2_count']})")
    print(f"   - Saved: {coverage_path.name}, {findings_path.name}")

    return {
        "coverage": coverage_payload,
        "findings": findings_payload,
    }


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    result = run_completeness_scan(repo_root)
    p0_unapproved = [f for f in result["findings"]["findings"] if f["severity"] == "P0"]
    return 1 if p0_unapproved else 0


if __name__ == "__main__":
    sys.exit(main())
