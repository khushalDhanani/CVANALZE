from __future__ import annotations

import pytest

from app.services.experience_calculator import ExperienceCalculator, ExperienceState
from app.services.job_taxonomy import CandidateResumeDTO


def test_experience_calculator_unparseable_dates_stay_unknown() -> None:
    """Workstream 3.3: Unknown employment dates remain unknown; duration is NOT invented from role count."""
    resume_json = {
        "work_experience": [
            {"job_title": "Software Developer", "company": "Acme Corp"},
            {"job_title": "Frontend Engineer", "company": "Beta LLC"},
        ]
    }

    res = ExperienceCalculator.calculate_canonical_experience(resume_json)

    assert res["authoritative_years"] is None
    assert res["experience_state"] == ExperienceState.UNKNOWN
    assert res["gross_display"] == "Experience Present (Dates Unparseable)"


def test_distinct_evidence_channels() -> None:
    """Workstream 3.3: Distinct evidence channels (summary, experience_titles, responsibilities, skills, education) are preserved."""
    resume_json = {
        "summary": "Experienced Python Backend Developer.",
        "work_experience": [
            {
                "job_title": "Senior Python Developer",
                "company": "CloudScale",
                "responsibilities": ["Architected microservices using FastAPI"],
            }
        ],
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "education": [{"degree": "B.S. Computer Science", "institution": "MIT"}],
    }

    dto = CandidateResumeDTO.from_resume("CV text", resume_json)

    assert "Senior Python Developer" in dto.raw_experience_titles
    assert any("FastAPI" in r for r in dto.raw_responsibilities)
    assert "Python" in dto.raw_skills
    assert any("B.S." in e for e in dto.raw_education)
