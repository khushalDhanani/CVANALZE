import pytest
from app.services.experience_calculator import ExperienceCalculator
from app.services.resume_field_extractor import ResumeFieldExtractor


def test_date_range_regex_extraction():
    lines = [
        "Software Engineer at Google (2018 - 2021)",
        "Senior Developer - Tech Corp 2019-2022",
        "Lead Engineer | Acme Inc. 15/06/2018 - 20/12/2021",
        "Fullstack Engineer - Acme 2020 to Present",
        "Backend Developer - Beta Corp 2018 - 21",
        "Intern - Startup Q1 2020 - Q4 2020",
    ]

    jobs = ResumeFieldExtractor._extract_employment(lines)
    assert len(jobs) >= 4
    dates_found = [j.get("dates") for j in jobs if j.get("dates")]
    assert len(dates_found) >= 4


def test_experience_calculator_date_formats():
    resume_json = {
        "work_experience": [
            {"job_title": "Software Engineer", "company": "Co 1", "dates": "2018 - 2020"},
            {"job_title": "Senior Engineer", "company": "Co 2", "dates": "2021 - Present"},
        ]
    }

    years = ExperienceCalculator.calculate_total_experience(resume_json)
    assert years >= 6.0


def test_unspaced_hyphen_and_short_years():
    resume_json = {
        "work_experience": [
            {"job_title": "Developer", "company": "Co", "dates": "2018-2021"},
        ]
    }
    years = ExperienceCalculator.calculate_total_experience(resume_json)
    assert 3.5 <= years <= 4.2
