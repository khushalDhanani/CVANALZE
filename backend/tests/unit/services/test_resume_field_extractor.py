from __future__ import annotations

from app.services.resume_field_extractor import ResumeFieldExtractor


def test_extract_candidate_name_from_header() -> None:
    lines = [
        "CURRICULUM VITAE",
        "## SARAH JANE CONNOR",
        "Senior Automation Engineer",
        "sarah.connor@example.com",
        "+1 555-432-1098",
        "Los Angeles, CA",
    ]
    name, confidence, confidence_level, source = ResumeFieldExtractor.extract_candidate_name(
        lines,
        email="sarah.connor@example.com",
        phone="+1 555-432-1098",
        location="Los Angeles, CA",
    )
    assert "SARAH" in name.upper()
    assert "CONNOR" in name.upper()
    assert "CURRICULUM" not in name.upper()
    assert "ENGINEER" not in name.upper()
    assert confidence >= 0.5


def test_is_valid_company_name_rejections() -> None:
    # Company names should reject emails, phone numbers, URLs, and generic headers
    assert not ResumeFieldExtractor.is_valid_company_name("user@example.com")
    assert not ResumeFieldExtractor.is_valid_company_name("+1 555-019-2834")
    assert not ResumeFieldExtractor.is_valid_company_name("https://example.com/profile")
    assert not ResumeFieldExtractor.is_valid_company_name("EDUCATION")

    # Valid company names should pass
    assert ResumeFieldExtractor.is_valid_company_name("Microsoft Corporation")
    assert ResumeFieldExtractor.is_valid_company_name("Tata Consultancy Services")
    assert ResumeFieldExtractor.is_valid_company_name("Acme Solutions Pvt Ltd")


def test_split_sections_routing() -> None:
    lines = [
        "John Doe",
        "## SUMMARY",
        "Experienced software developer.",
        "## WORK EXPERIENCE",
        "Software Engineer | Acme Corp | Jan 2020 - Dec 2022",
        "- Built microservices",
        "## EDUCATION",
        "B.S. in Computer Science | MIT | 2016 - 2020",
        "## SKILLS",
        "Python, Docker, SQL",
    ]
    sections = ResumeFieldExtractor._split_sections(lines)
    assert "experience" in sections or "work experience" in sections or "work" in sections
    assert "education" in sections
    assert "skills" in sections


def test_extract_skills_from_text() -> None:
    skills_lines = [
        "Programming Languages: Python, JavaScript, Go",
        "Databases & Frameworks: PostgreSQL, Docker, FastAPI",
    ]
    skills_result = ResumeFieldExtractor._extract_skills(skills_lines)
    assert isinstance(skills_result, dict)
    assert "all_skills" in skills_result or len(skills_result) > 0
