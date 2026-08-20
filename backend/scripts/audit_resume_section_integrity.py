#!/usr/bin/env python3
"""Audit stored CV results for section-integrity compatibility.

The default mode is deliberately read-only. Reprocessing is opt-in and delegates
to the existing administrator API so queueing, locking, identity, and source-file
validation remain centralized in the application.
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any
from urllib import error, parse, request

MAX_BATCH_SIZE = 1_000
INTEGRITY_POLICY_PREFIX = "section-integrity"
CURRENT_EXTRACTION_PARSER_VERSION = os.getenv("EXTRACTION_PARSER_VERSION", "1.2.0")
CURRENT_EXTRACTION_SCHEMA_VERSION = os.getenv("EXTRACTION_SCHEMA_VERSION", "2.1.0")
SECTION_LABELS = {
    "contact", "profile", "summary", "education", "educational background",
    "work experience", "experience", "projects", "technical skills", "skills",
    "safety and compliance", "core competencies", "languages", "interests", "declaration",
}
EDUCATION_QUALIFICATION = re.compile(
    r"\b(?:b\.?\s*e\.?|b\.?\s*tech|b\.?\s*sc|bca|bba|b\.?\s*com|b\.?\s*a\.?|"
    r"m\.?\s*e\.?|m\.?\s*tech|m\.?\s*sc|mca|mba|m\.?\s*com|ph\.?\s*d|diploma|iti|"
    r"h\.?\s*s\.?\s*c|s\.?\s*s\.?\s*c|10th|12th|bachelor|master|doctorate)\b",
    re.IGNORECASE,
)
EMPLOYMENT_DATE_RANGE = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\s*"
    r"(?:-|–|—|to|till|until)\s*(?:present|current|till date|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4})\b",
    re.IGNORECASE,
)
EMPLOYMENT_TITLE = re.compile(
    r"\b(?:engineer|manager|officer|supervisor|executive|analyst|consultant|developer|lead|head|"
    r"coordinator|operator|technician|specialist|in-charge)\b",
    re.IGNORECASE,
)
RECOVERED_SKILL_CATEGORY = re.compile(
    r"^recover(?:ed|y)\b.*\b(?:skills?|stats?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AuditSummary:
    scanned: int
    requires_reprocessing: int
    reprocessed: int
    reason_counts: dict[str, int]
    next_cursor: str | None
    candidate_ids: tuple[str, ...] = ()


def _is_historical_result(path: Path) -> bool:
    return path.stem.casefold().endswith(("_enriched", "_reprocessed", "_latest"))


def _bounded_result_paths(
    results_dir: Path, *, batch_size: int, cursor: str | None
) -> tuple[list[Path], bool]:
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError(f"batch_size must be between 1 and {MAX_BATCH_SIZE}")
    if not results_dir.is_dir():
        raise ValueError(f"results_dir is not a directory: {results_dir}")

    eligible = (
        entry
        for entry in results_dir.iterdir()
        if entry.is_file()
        and not entry.is_symlink()
        and entry.suffix.lower() == ".json"
        and not _is_historical_result(entry)
        and (cursor is None or entry.name > cursor)
    )
    selected = heapq.nsmallest(batch_size + 1, eligible, key=lambda path: path.name)
    return selected[:batch_size], len(selected) > batch_size


def _audit_reasons(payload: Any) -> set[str]:
    if not isinstance(payload, dict):
        return {"MALFORMED_RESULT"}

    reasons: set[str] = set()
    resume_json_for_skills = payload.get("resume_json")
    skills = resume_json_for_skills.get("skills") if isinstance(resume_json_for_skills, dict) else None
    categorized = skills.get("categorized") if isinstance(skills, dict) else None
    if isinstance(categorized, dict) and any(
        RECOVERED_SKILL_CATEGORY.search(str(category).strip())
        for category in categorized
    ):
        reasons.add("UNSAFE_RECOVERED_SKILLS")
    if payload.get("parser_version") != CURRENT_EXTRACTION_PARSER_VERSION:
        reasons.add("LEGACY_EXTRACTION_PARSER")
    if payload.get("schema_version") != CURRENT_EXTRACTION_SCHEMA_VERSION:
        reasons.add("LEGACY_EXTRACTION_SCHEMA")

    integrity = payload.get("extraction_integrity")
    policy = integrity.get("policy_version") if isinstance(integrity, dict) else None
    if not isinstance(policy, str) or not policy.startswith(INTEGRITY_POLICY_PREFIX):
        reasons.add("MISSING_INTEGRITY_METADATA")
        return reasons

    accepted_counts = integrity.get("accepted_counts")
    resume_json = payload.get("resume_json")
    normalized_resume = payload.get("normalized_resume")
    if (
        not isinstance(accepted_counts, dict)
        or not isinstance(resume_json, dict)
        or not isinstance(normalized_resume, dict)
    ):
        reasons.add("MALFORMED_ACCEPTED_COLLECTION")
        return reasons
    for field in ("education", "projects"):
        records = resume_json.get(field)
        expected_count = accepted_counts.get(field)
        if not isinstance(records, list) or not isinstance(expected_count, int) or expected_count < 0:
            reasons.add("MALFORMED_ACCEPTED_COLLECTION")
            continue
        if len(records) != expected_count:
            reasons.add("INTEGRITY_COUNT_MISMATCH")
        if any(
            not isinstance(item, dict) or item.get("source_section") != field
            for item in records
        ):
            reasons.add("INVALID_SOURCE_PROVENANCE")
        normalized_records = normalized_resume.get(field)
        if not isinstance(normalized_records, list) or len(normalized_records) != expected_count:
            reasons.add("NORMALIZED_PROJECTION_MISMATCH")
        elif any(
            not isinstance(item, dict) or item.get("source_section") != field
            for item in normalized_records
        ):
            reasons.add("NORMALIZED_PROJECTION_MISMATCH")
        else:
            primary_key = "degree" if field == "education" else "name"
            for raw_item, normalized_item in zip(records, normalized_records, strict=True):
                if not isinstance(raw_item, dict) or not isinstance(normalized_item, dict):
                    continue
                raw_primary = str(raw_item.get(primary_key) or raw_item.get("title") or "").strip()
                evidence = normalized_item.get("evidence")
                if raw_primary and (
                    not isinstance(evidence, list)
                    or raw_primary not in {str(value).strip() for value in evidence}
                ):
                    reasons.add("NORMALIZED_PROJECTION_MISMATCH")
                    break

        for item in records:
            if not isinstance(item, dict):
                continue
            primary_value = str(
                item.get("institution") if field == "education" else item.get("name") or item.get("title") or ""
            ).strip().casefold().replace("&", "and")
            primary_value = " ".join(primary_value.split())
            if primary_value in SECTION_LABELS:
                reasons.add("INVALID_ACCEPTED_RECORD")
            if field == "education" and not EDUCATION_QUALIFICATION.search(
                str(item.get("degree") or "")
            ):
                reasons.add("INVALID_ACCEPTED_RECORD")
            if field == "projects" and EMPLOYMENT_TITLE.search(primary_value) and EMPLOYMENT_DATE_RANGE.search(
                str(item.get("description") or "")
            ):
                reasons.add("INVALID_ACCEPTED_RECORD")

    expected_skill_count = accepted_counts.get("skills")
    raw_skills = resume_json.get("skills")
    raw_skill_values = raw_skills.get("all_skills") if isinstance(raw_skills, dict) else None
    normalized_skills = normalized_resume.get("skills")
    if (
        not isinstance(expected_skill_count, int)
        or expected_skill_count < 0
        or not isinstance(raw_skill_values, list)
        or not isinstance(normalized_skills, list)
    ):
        reasons.add("MALFORMED_ACCEPTED_COLLECTION")
    elif len(raw_skill_values) != expected_skill_count:
        reasons.add("INTEGRITY_COUNT_MISMATCH")
    elif len(normalized_skills) != expected_skill_count:
        reasons.add("NORMALIZED_PROJECTION_MISMATCH")
    return reasons


def audit_results(
    *, results_dir: Path, batch_size: int = 100, cursor: str | None = None
) -> AuditSummary:
    """Audit one stable, bounded batch without changing files or external state."""

    paths, has_more = _bounded_result_paths(results_dir, batch_size=batch_size, cursor=cursor)
    reason_counts: Counter[str] = Counter()
    affected: list[str] = []

    for path in paths:
        payload: Any = None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            reasons = _audit_reasons(payload)
        except (OSError, UnicodeError, json.JSONDecodeError):
            reasons = {"MALFORMED_RESULT"}

        if reasons:
            canonical_id = (
                str(payload.get("id") or payload.get("scan_id") or payload.get("candidate_id") or path.stem)
                if isinstance(payload, dict)
                else path.stem
            )
            if canonical_id not in affected:
                affected.append(canonical_id)
            reason_counts.update(reasons)

    return AuditSummary(
        scanned=len(paths),
        requires_reprocessing=len(affected),
        reprocessed=0,
        reason_counts=dict(sorted(reason_counts.items())),
        next_cursor=paths[-1].name if paths and has_more else None,
        candidate_ids=tuple(affected),
    )


def queue_reprocessing(
    candidate_ids: tuple[str, ...],
    *,
    api_base_url: str,
    api_key: str | None = None,
    timeout_seconds: float = 10.0,
) -> int:
    """Queue candidates through the existing API; never rewrite result files."""

    queued = 0
    base = api_base_url.rstrip("/")
    for candidate_id in candidate_ids:
        url = f"{base}/api/v1/candidates/{parse.quote(candidate_id, safe='')}/reprocess"
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        api_request = request.Request(url, method="POST", headers=headers)
        try:
            with request.urlopen(api_request, timeout=timeout_seconds) as response:  # noqa: S310
                if 200 <= response.status < 300:
                    queued += 1
        except (error.HTTPError, error.URLError, TimeoutError):
            continue
    return queued


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--cursor")
    parser.add_argument("--reprocess", action="store_true", help="Queue affected candidates through the API")
    parser.add_argument("--api-base-url")
    parser.add_argument(
        "--api-key",
        default=os.getenv("CV_AUDIT_API_KEY"),
        help="Administrator API key; defaults to CV_AUDIT_API_KEY",
    )
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.reprocess and not args.api_base_url:
        raise SystemExit("--api-base-url is required with --reprocess")

    summary = audit_results(results_dir=args.results_dir, batch_size=args.batch_size, cursor=args.cursor)
    if args.reprocess:
        queued = queue_reprocessing(
            summary.candidate_ids,
            api_base_url=args.api_base_url,
            api_key=args.api_key,
            timeout_seconds=args.timeout_seconds,
        )
        summary = replace(summary, reprocessed=queued)

    public_summary = asdict(summary)
    public_summary.pop("candidate_ids")
    print(json.dumps(public_summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
