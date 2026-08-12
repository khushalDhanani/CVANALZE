from datetime import datetime

from app.services.experience_calculator import ExperienceCalculator


def test_parse_date():
    assert ExperienceCalculator._parse_date("Jan 2021") == datetime(2021, 1, 1)
    assert ExperienceCalculator._parse_date("01/2021") == datetime(2021, 1, 1)
    assert ExperienceCalculator._parse_date("2021-01") == datetime(2021, 1, 1)
    assert ExperienceCalculator._parse_date("2021", is_end_date=False) == datetime(2021, 1, 1)
    assert ExperienceCalculator._parse_date("2021", is_end_date=True) == datetime(2021, 12, 31)

    present_date = ExperienceCalculator._parse_date("Present")
    assert present_date is not None
    assert present_date.year == datetime.now().year
    assert present_date.month == datetime.now().month


def test_extract_date_range():
    start, end = ExperienceCalculator._extract_date_range("Jan 2021 - Dec 2021")
    assert start == datetime(2021, 1, 1)
    assert end == datetime(2021, 12, 31)

    start, end = ExperienceCalculator._extract_date_range("2021")
    assert start == datetime(2021, 1, 1)
    assert end == datetime(2021, 12, 31)


def test_calculate_total_experience_simple():
    resume_json = {
        "work_experience": [
            {"dates": "Jan 2020 - Dec 2021"},  # 24 full months -> Jan 1, 2020 to Dec 31, 2021 = 2.0 full years
        ]
    }
    exp = ExperienceCalculator.calculate_total_experience(resume_json)
    assert exp == 2.0


def test_calculate_total_experience_overlapping():
    resume_json = {
        "work_experience": [
            {"dates": "Jan 2020 - Dec 2021"},  # 2020-01-01 to 2021-12-31
            {"dates": "Jun 2021 - Dec 2022"},  # 2021-06-01 to 2022-12-31
        ]
    }
    # Merged interval: 2020-01-01 to 2022-12-31 = 3.0 full years
    exp = ExperienceCalculator.calculate_total_experience(resume_json)
    assert exp == 3.0


def test_calculate_total_experience_explicit_override():
    resume_json = {
        "work_experience": [
            {"dates": "Jan 2020 - Dec 2021"},
        ]
    }
    cv_text = "Total Experience: 4.5 years"
    exp = ExperienceCalculator.calculate_total_experience(resume_json, cv_text)
    assert exp == 2.0

    # Close stated values validate the dates but never override them.
    cv_text = "Total Experience: 2.0 years"
    exp = ExperienceCalculator.calculate_total_experience(resume_json, cv_text)
    assert exp == 2.0
