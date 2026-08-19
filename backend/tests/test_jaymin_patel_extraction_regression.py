from __future__ import annotations
import pytest

from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.resume_text_normalizer import ResumeTextNormalizer


def test_resume_text_normalizer_unescapes_html_entities() -> None:
    raw = "React &amp; React Native Developer &amp; AI Engineer"
    cleaned = ResumeTextNormalizer.sanitize(raw)
    assert "&amp;" not in cleaned
    assert "React & React Native Developer & AI Engineer" in cleaned


def test_resume_field_extractor_extracts_jaymin_patel_name() -> None:
    text_lines = [
        "AI Engineer & Full Stack Developer",
        "Sr. Software Developer - AI & Mobile",
        "React & React Native Developer",
        "React & React Native Team Leader",
        "## JAYMIN PATEL",
        "AI Engineer & Full Stack Developer",
        "+91 75750 69128",
        "jayminPatel4998@gmail.com",
        "India",
    ]
    name, confidence, confidence_level, source = ResumeFieldExtractor.extract_candidate_name(
        text_lines,
        email="jayminPatel4998@gmail.com",
        phone="+91 75750 69128",
        location="India",
    )
    assert "React" not in name
    assert "Developer" not in name
    assert "JAYMIN" in name.upper()
    assert "PATEL" in name.upper()


def test_is_valid_company_name_rejects_phone_numbers_and_emails() -> None:
    assert not ResumeFieldExtractor.is_valid_company_name("+91 75750 69128")
    assert not ResumeFieldExtractor.is_valid_company_name("jayminPatel4998@gmail.com")
    assert not ResumeFieldExtractor.is_valid_company_name("http://example.com")
    assert ResumeFieldExtractor.is_valid_company_name("Jack Solutions")


def test_split_sections_routes_key_project_experience_to_projects() -> None:
    lines = [
        "## WORK EXPERIENCE",
        "PopWay | Mar 2019 - Sep 2019",
        "## KEY PROJECT EXPERIENCE",
        "## Azure Data Integration | ADF architecture awareness",
    ]
    sections = ResumeFieldExtractor._split_sections(lines)
    assert "projects" in sections
    assert len(sections["projects"]) >= 1
    assert "Azure Data Integration" in sections["projects"][0]
