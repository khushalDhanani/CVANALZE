from __future__ import annotations

from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.cv import CVProcessingResponse
from app.schemas.normalized_resume import (
    NormalizedContact,
    NormalizedDateInterval,
    NormalizedEducation,
    NormalizedEmployment,
    NormalizedResume,
    NormalizedSkill,
    NormalizedStringField,
)


def test_normalized_string_field() -> None:
    field = NormalizedStringField(
        raw_value="Sr. Software Engineer",
        normalized_value="Senior Software Engineer",
        confidence=0.95,
        evidence=["Worked as Sr. Software Engineer from 2020-2023"],
    )
    assert str(field) == "Senior Software Engineer"
    assert field == "Sr. Software Engineer"
    assert field == "Senior Software Engineer"
    assert field.confidence == 0.95


def test_normalized_date_interval() -> None:
    interval = NormalizedDateInterval(
        raw_value="Jan 2020 - Dec 2022",
        start_date="2020-01-01",
        end_date="2022-12-31",
        is_current=False,
        duration_months=36,
        confidence=0.9,
    )
    assert interval.duration_months == 36
    assert interval.is_current is False
    assert interval.start_date == "2020-01-01"


def test_normalized_resume_model() -> None:
    resume = NormalizedResume(
        contact=NormalizedContact(
            email=NormalizedStringField(raw_value="alex@example.com", normalized_value="alex@example.com", confidence=1.0),
            phone=NormalizedStringField(raw_value="+1 555-0199", normalized_value="+15550199", confidence=0.9),
        ),
        skills=[
            NormalizedSkill(raw_value="python", normalized_value="Python", confidence=0.95, aliases=["py"]),
            NormalizedSkill(raw_value="fastapi", normalized_value="FastAPI", confidence=0.9),
        ],
        employment=[
            NormalizedEmployment(
                job_title=NormalizedStringField(raw_value="Developer", normalized_value="Software Developer", confidence=0.9),
                company=NormalizedStringField(raw_value="Acme Corp", normalized_value="Acme Corp", confidence=0.9),
                interval=NormalizedDateInterval(duration_months=24, is_current=True),
            )
        ],
        education=[
            NormalizedEducation(
                degree=NormalizedStringField(raw_value="B.S. CS", normalized_value="Bachelor of Science in Computer Science", confidence=0.9),
                institution=NormalizedStringField(raw_value="UC Berkeley", normalized_value="UC Berkeley", confidence=0.9),
            )
        ],
    )
    assert str(resume.contact.email) == "alex@example.com"
    assert len(resume.skills) == 2
    assert len(resume.employment) == 1
    assert len(resume.education) == 1


def test_cv_processing_response_schema() -> None:
    resp = CVProcessingResponse(
        message="CV processed successfully",
        cv_key="cv-hash-123456",
        status="completed",
        progress=100,
        stage="COMPLETED",
        job_id="job-uuid-789",
        job_state="COMPLETED",
    )
    assert resp.cv_key == "cv-hash-123456"
    assert resp.status == "completed"
    assert resp.progress == 100
