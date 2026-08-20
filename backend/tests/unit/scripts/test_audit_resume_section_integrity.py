from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_resume_section_integrity import audit_results


def test_audit_defaults_to_read_only_and_reports_legacy_integrity_anomalies(tmp_path: Path) -> None:
    (tmp_path / "candidate-a.json").write_text(
        json.dumps(
            {
                "parser_version": "1.0.0",
                "schema_version": "2.0.0",
                "resume_json": {
                    "projects": [{"name": "Declaration", "description": "Text"}],
                    "education": [{"institution": "Work Experience"}],
                },
            }
        ),
        encoding="utf-8",
    )

    result = audit_results(results_dir=tmp_path, batch_size=100)

    assert result.scanned == 1
    assert result.requires_reprocessing == 1
    assert result.reprocessed == 0
    assert result.reason_counts == {
        "LEGACY_EXTRACTION_PARSER": 1,
        "LEGACY_EXTRACTION_SCHEMA": 1,
        "MISSING_INTEGRITY_METADATA": 1,
    }
    assert result.next_cursor is None


def test_audit_bounds_batch_size(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="batch_size"):
        audit_results(results_dir=tmp_path, batch_size=1001)


def test_audit_accepts_current_schema_with_integrity_policy_version(tmp_path: Path) -> None:
    (tmp_path / "candidate-current.json").write_text(
        json.dumps(
            {
                "parser_version": "1.2.0",
                "schema_version": "2.1.0",
                "extraction_integrity": {
                    "policy_version": "section-integrity-1.0.0",
                    "accepted_counts": {"education": 0, "projects": 0, "skills": 0},
                },
                "resume_json": {
                    "education": [],
                    "projects": [],
                    "skills": {"all_skills": [], "categorized": {}},
                },
                "normalized_resume": {"education": [], "projects": [], "skills": []},
            }
        ),
        encoding="utf-8",
    )

    result = audit_results(results_dir=tmp_path)

    assert result.requires_reprocessing == 0
    assert result.reason_counts == {}


def test_audit_flags_old_parser_even_when_schema_is_current(tmp_path: Path) -> None:
    (tmp_path / "candidate-old-parser.json").write_text(
        json.dumps(
            {
                "parser_version": "1.0.0",
                "schema_version": "2.1.0",
                "extraction_integrity": {
                    "policy_version": "section-integrity-1.0.0",
                    "accepted_counts": {"education": 0, "projects": 0, "skills": 0},
                },
                "resume_json": {
                    "education": [],
                    "projects": [],
                    "skills": {"all_skills": [], "categorized": {}},
                },
                "normalized_resume": {"education": [], "projects": [], "skills": []},
            }
        ),
        encoding="utf-8",
    )

    result = audit_results(results_dir=tmp_path)

    assert result.reason_counts == {"LEGACY_EXTRACTION_PARSER": 1}


def test_audit_skips_historical_files_and_detects_count_or_provenance_corruption(tmp_path: Path) -> None:
    payload = {
        "id": "canonical-candidate",
        "parser_version": "1.2.0",
        "schema_version": "2.1.0",
        "extraction_integrity": {
            "policy_version": "section-integrity-1.0.0",
            "accepted_counts": {"education": 1, "projects": 0, "skills": 0},
        },
        "resume_json": {
            "education": [{"degree": "B.E.", "source_section": "experience"}],
            "projects": [],
            "skills": {"all_skills": [], "categorized": {}},
        },
        "normalized_resume": {
            "education": [
                {
                    "degree": {"normalized_value": "B.E."},
                    "evidence": ["B.E."],
                    "source_section": "education",
                }
            ],
            "projects": [],
            "skills": [],
        },
    }
    (tmp_path / "candidate.json").write_text(json.dumps(payload), encoding="utf-8")
    (tmp_path / "candidate_latest.json").write_text(json.dumps(payload), encoding="utf-8")

    result = audit_results(results_dir=tmp_path, batch_size=1)

    assert result.scanned == 1
    assert result.candidate_ids == ("canonical-candidate",)
    assert result.reason_counts == {"INVALID_SOURCE_PROVENANCE": 1}
    assert result.next_cursor is None


def test_audit_detects_semantic_and_normalized_projection_corruption(tmp_path: Path) -> None:
    (tmp_path / "candidate.json").write_text(
        json.dumps(
            {
                "parser_version": "1.2.0",
                "schema_version": "2.1.0",
                "extraction_integrity": {
                    "policy_version": "section-integrity-1.0.0",
                    "accepted_counts": {"education": 0, "projects": 1, "skills": 0},
                },
                "resume_json": {
                    "education": [],
                    "projects": [
                        {"name": "Declaration", "description": "Text", "source_section": "projects"}
                    ],
                    "skills": {"all_skills": [], "categorized": {}},
                },
                "normalized_resume": {"education": [], "projects": [], "skills": []},
            }
        ),
        encoding="utf-8",
    )

    result = audit_results(results_dir=tmp_path)

    assert result.reason_counts == {
        "INVALID_ACCEPTED_RECORD": 1,
        "NORMALIZED_PROJECTION_MISMATCH": 1,
    }


def test_audit_detects_employment_project_and_education_without_qualification(tmp_path: Path) -> None:
    (tmp_path / "candidate.json").write_text(
        json.dumps(
            {
                "parser_version": "1.2.0",
                "schema_version": "2.1.0",
                "extraction_integrity": {
                    "policy_version": "section-integrity-1.0.0",
                    "accepted_counts": {"education": 1, "projects": 1, "skills": 0},
                },
                "resume_json": {
                    "education": [
                        {"institution": "Example University", "source_section": "education"}
                    ],
                    "projects": [
                        {
                            "name": "Shift Engineer",
                            "description": "Example Ltd | March 2021 - March 2024",
                            "source_section": "projects",
                        }
                    ],
                    "skills": {"all_skills": [], "categorized": {}},
                },
                "normalized_resume": {
                    "education": [
                        {
                            "evidence": ["Example University"],
                            "source_section": "education",
                        }
                    ],
                    "projects": [
                        {
                            "evidence": ["Shift Engineer"],
                            "source_section": "projects",
                        }
                    ],
                    "skills": [],
                },
            }
        ),
        encoding="utf-8",
    )

    result = audit_results(results_dir=tmp_path)

    assert result.reason_counts == {"INVALID_ACCEPTED_RECORD": 1}


def test_audit_flags_legacy_recovered_context_skills_even_with_current_versions(tmp_path: Path) -> None:
    (tmp_path / "candidate.json").write_text(
        json.dumps(
            {
                "parser_version": "1.2.0",
                "schema_version": "2.1.0",
                "extraction_integrity": {
                    "policy_version": "section-integrity-1.0.0",
                    "accepted_counts": {"education": 0, "projects": 0, "skills": 2},
                },
                "resume_json": {
                    "education": [],
                    "projects": [],
                    "skills": {
                        "all_skills": ["Sample Candidate", "Address"],
                        "categorized": {
                            "Recovered Context Skills": ["Sample Candidate"],
                            "Recovery Stats": ["Address"],
                        },
                    },
                },
                "normalized_resume": {
                    "education": [],
                    "projects": [],
                    "skills": [
                        {"normalized_value": "Sample Candidate"},
                        {"normalized_value": "Address"},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    result = audit_results(results_dir=tmp_path)

    assert result.reason_counts == {"UNSAFE_RECOVERED_SKILLS": 1}


def test_audit_rejects_current_results_without_skill_integrity_contract(tmp_path: Path) -> None:
    (tmp_path / "candidate.json").write_text(
        json.dumps(
            {
                "parser_version": "1.2.0",
                "schema_version": "2.1.0",
                "extraction_integrity": {
                    "policy_version": "section-integrity-1.0.0",
                    "accepted_counts": {"education": 0, "projects": 0},
                },
                "resume_json": {"education": [], "projects": []},
                "normalized_resume": {"education": [], "projects": []},
            }
        ),
        encoding="utf-8",
    )

    result = audit_results(results_dir=tmp_path)

    assert result.reason_counts == {"MALFORMED_ACCEPTED_COLLECTION": 1}
