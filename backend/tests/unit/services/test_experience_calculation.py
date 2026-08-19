from __future__ import annotations

from datetime import datetime

from app.services.date_interval_parser import DateIntervalParser
from app.services.experience_calculator import ExperienceCalculator, ExperienceState


def test_date_interval_parser_fixed_dates() -> None:
    interval = DateIntervalParser.parse_interval("Jan 2020 - Dec 2022")
    assert interval.start_date is not None
    assert interval.end_date is not None
    assert interval.is_current is False
    assert interval.duration_months == 36


def test_date_interval_parser_present_role() -> None:
    ref_date = datetime(2024, 6, 1)
    interval = DateIntervalParser.parse_interval("June 2022 - Present", ref_date=ref_date)
    assert interval.is_current is True
    assert interval.duration_months == 25


def test_date_interval_parser_is_present_keywords() -> None:
    assert DateIntervalParser.is_present("Present") is True
    assert DateIntervalParser.is_present("Current") is True
    assert DateIntervalParser.is_present("till date") is True
    assert DateIntervalParser.is_present("Jan 2020") is False


def test_experience_calculator_merges_overlapping_intervals() -> None:
    import pytest
    # Role A: 2020-01 to 2022-01 (25 months inclusive)
    # Role B: 2021-01 to 2023-01 (25 months inclusive, with overlap)
    # Total merged duration: 2020-01 to 2023-01 = 37 months = 3.1 years
    resume_json = {
        "work_experience": [
            {"job_title": "Developer A", "company": "Company A", "dates": "Jan 2020 - Jan 2022"},
            {"job_title": "Developer B", "company": "Company B", "dates": "Jan 2021 - Jan 2023"},
        ]
    }
    result = ExperienceCalculator.calculate_canonical_experience(resume_json)
    assert result["experience_state"] == ExperienceState.CALCULATED
    assert result["total_experience_years"] == pytest.approx(3.1, rel=0.1)


def test_experience_calculator_empty_cv_yields_unknown_or_zero() -> None:
    empty_resume: dict = {"work_experience": []}
    result = ExperienceCalculator.calculate_canonical_experience(empty_resume, cv_text="Fresh graduate with no prior experience.")
    assert result["experience_state"] in (ExperienceState.ZERO_CONFIRMED, ExperienceState.UNKNOWN)
