import re
from datetime import datetime
import pytest

from app.services.experience_calculator import ExperienceCalculator
from app.services.resume_field_extractor import ResumeFieldExtractor


def test_real_candidate_utkarsh_patil_dates():
    """
    Test real candidate Utkarsh Patil's CV structure:
    Role 1: 'Pulse Software Solutions LLC - ASP .NET Developer'
    Role 2: '07/2021 - Present | Projects/Tasks'
    Role 3 (Education date pattern): '06/2017 - 07/2020'
    """
    lines = [
        "Pulse Software Solutions LLC - ASP .NET Developer",
        "07/2021 - Present",
        "- Team Locum (Healthcare Recruitment Agency): Migrated a Ruby on Rails project to ASP.NET Core",
        "- Managed database operations with MongoDB",
    ]

    jobs = ResumeFieldExtractor._extract_employment(lines)
    assert len(jobs) >= 1
    # Ensure role header and date line were joined rather than split into empty date entry
    first_job = jobs[0]
    assert first_job.get("dates") == "07/2021 - Present"
    assert "Pulse Software Solutions" in (first_job.get("company") or "") or "ASP .NET Developer" in (first_job.get("job_title") or "")


def test_canonical_experience_calculation_utkarsh_patil():
    resume_json = {
        "work_experience": [
            {
                "company": "Pulse Software Solutions LLC",
                "job_title": "ASP .NET Developer",
                "dates": "07/2021 - Present",
            }
        ]
    }

    summary = ExperienceCalculator.calculate_canonical_experience(
        resume_json, cv_text="4.0 years of experience", candidate_id="utkarsh_test"
    )

    # 07/2021 to Present (Aug 2026) is approx 5.1 years
    assert summary["experience_years"] >= 4.0
    assert summary["seniority"] in ("Senior", "Mid-Level")
    assert "Assessed as" in summary["experience_assessment"]
    assert len(summary["normalized_employment"]) == 1
    assert summary["normalized_employment"][0]["is_current"] is True


def test_unsupported_date_logging(caplog):
    """Verify that unparseable date strings log a warning with candidate ID and role index."""
    resume_json = {
        "work_experience": [
            {
                "company": "Tech Corp",
                "job_title": "Developer",
                "dates": "INVALID_DATE_ABC_XYZ",
            }
        ]
    }

    summary = ExperienceCalculator.calculate_canonical_experience(
        resume_json, cv_text="", candidate_id="cand_12345"
    )

    # Should log warning with candidate ID and role index #1
    assert any("[EXPERIENCE_DATE_PARSE_UNSUPPORTED]" in record.message for record in caplog.records)
    assert "cand_12345" in caplog.text
    assert "Role #1" in caplog.text
    assert summary["unparsed_dates"] == [{"role_index": 1, "raw_dates": "INVALID_DATE_ABC_XYZ", "job_title": "Developer"}]
    # Should fall back to role count heuristic (1.0 years) instead of 0.0 Junior
    assert summary["experience_years"] == 1.0
    assert summary["seniority"] == "Junior / Associate"


def test_overlapping_and_same_month_roles():
    """
    Test that concurrent roles do not double count years,
    and same-month roles count as at least 1 month.
    """
    resume_json = {
        "work_experience": [
            {"job_title": "Role 1", "dates": "01/2020 - 12/2020"},
            {"job_title": "Role 2 (Concurrent)", "dates": "06/2020 - 12/2020"},
            {"job_title": "Role 3 (Same Month)", "dates": "05/2021 - 05/2021"},
        ]
    }

    summary = ExperienceCalculator.calculate_canonical_experience(resume_json)

    # Role 1 & 2 overlap: 01/2020 - 12/2020 = 1.0 year (not 1.5 years)
    # Role 3: 05/2021 - 05/2021 = 1 month (0.1 year)
    # Total unique active time: ~1.1 years
    assert 1.0 <= summary["experience_years"] <= 1.2
    assert summary["merged_intervals_count"] == 2
