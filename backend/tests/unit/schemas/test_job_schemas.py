from __future__ import annotations

from app.schemas.domain import DepartmentDomain, KeywordConfig, MatchType
from app.schemas.job import JobOpening


def test_job_opening_schema_validation() -> None:
    job = JobOpening(
        id="job-101",
        title="Full Stack Engineer",
        department="Engineering",
        required_skills=["Python", "React", "Docker"],
        preferred_keywords=["PostgreSQL", "Redis"],
        min_experience_years=3.0,
        max_experience_years=7.0,
        domain="Information Technology & Software",
        job_family="Software Engineering & Development",
    )
    assert job.id == "job-101"
    assert job.title == "Full Stack Engineer"
    assert len(job.required_skills) == 3
    assert job.min_experience_years == 3.0
    assert job.required_skills_are_mandatory is True


def test_department_domain_schema_parsing() -> None:
    raw_domain = {
        "id": 1,
        "department_id": 9,
        "department_name": "CIS Team",
        "domain_name": "Information Technology & Software",
        "keywords": [
            "developer",
            {"term": "IT", "match_type": "CASE_SENSITIVE_ACRONYM", "weight": 1.5},
        ],
        "default_roles": ["Software Developer", "DevOps Engineer"],
        "priority": 1,
        "is_active": True,
    }
    domain = DepartmentDomain.model_validate(raw_domain)
    assert domain.department_name == "CIS Team"
    assert len(domain.keywords) == 2
    assert domain.keywords[0].term == "developer"
    assert domain.keywords[1].term == "IT"
    assert domain.keywords[1].match_type == MatchType.CASE_SENSITIVE_ACRONYM
    assert domain.keywords[1].weight == 1.5
