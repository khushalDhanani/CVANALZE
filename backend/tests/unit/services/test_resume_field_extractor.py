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
    lines = ["Python", "FastAPI", "PostgreSQL", "Docker"]
    skills = ResumeFieldExtractor._extract_skills(lines)
    assert isinstance(skills, dict)
    assert len(skills) > 0


def test_job_title_rejects_roll_number_and_academic_ids() -> None:
    # Academic/administrative roll numbers and ID lines must strictly be rejected
    assert not ResumeFieldExtractor.is_valid_job_title("Roll No.: 21111003")
    assert not ResumeFieldExtractor.is_valid_job_title("Enrollment No: 19827341")
    assert not ResumeFieldExtractor.is_valid_job_title("PRN No. 20210123")
    assert not ResumeFieldExtractor.is_valid_job_title("CPI: 8.57/10")
    assert not ResumeFieldExtractor.is_valid_job_title("Mobile: +91 9999999999")
    assert not ResumeFieldExtractor.is_valid_job_title("Reg. No.: 449102")

    assert not ResumeFieldExtractor.is_structural_job_title_noun_phrase("Roll No.: 21111003")
    assert not ResumeFieldExtractor.is_structural_job_title_noun_phrase("PRN: 20210091")

    # Valid job titles should pass
    assert ResumeFieldExtractor.is_valid_job_title("Senior Software Engineer")
    assert ResumeFieldExtractor.is_valid_job_title("Designation: Billing Executive")


def test_extract_title_from_summary_or_header_rejects_roll_number() -> None:
    lines = [
        "ABHISHEK DNYANESHWAR REVSKAR",
        "Roll No.: 21111003",
        "Indian Institute of Technology, Kanpur",
        "M.Tech Computer Science & Engineering",
    ]
    title = ResumeFieldExtractor.extract_title_from_summary_or_header(
        [], lines, candidate_name="ABHISHEK DNYANESHWAR REVSKAR"
    )
    assert title != "Roll No.: 21111003"
    assert title is None or "Roll" not in str(title)
