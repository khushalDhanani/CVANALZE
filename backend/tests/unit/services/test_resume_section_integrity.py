from __future__ import annotations

from app.core.config import settings
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.resume_normalizer import ResumeNormalizer
from app.services.resume_sections import ResumeSectionDetector, SectionKind

CHEMICAL_ENGINEER_MARKDOWN = """
## SAMPLE CANDIDATE

### Professional Profile Summary
Chemical engineer with production and plant commissioning experience.

### Educational Background

| Course | Board/University | Year of Passing | CGPA / Percentage |
|---|---|---|---|
| B.E. Chemical | GTU | 2019 | 7.59 CGPA |
| H.S.C | GHSEB | 2015 | 63% |
| S.S.C | GSEB | 2013 | 67.5% |

### Work Experience

#### Engineer (Process)
Example Chemicals Ltd | March 2025 – till date
- Maintained process parameters and safety compliance.

### Safety & Compliance
- Familiar with PSSR, HIRA, HAZOP, and JSA.

### Interests
Reading and trekking.

### Declaration
The information above is correct.
"""


def test_education_table_without_projects_does_not_cross_map_sections() -> None:
    result = ResumeFieldExtractor.extract(CHEMICAL_ENGINEER_MARKDOWN)

    assert result["projects"] == []
    assert result["education"] == [
        {
            "degree": "B.E. Chemical",
            "institution": "GTU",
            "dates": "2019",
            "grade": "7.59 CGPA",
            "source_section": "education",
            "source_heading": "Educational Background",
        },
        {
            "degree": "H.S.C",
            "institution": "GHSEB",
            "dates": "2015",
            "grade": "63%",
            "source_section": "education",
            "source_heading": "Educational Background",
        },
        {
            "degree": "S.S.C",
            "institution": "GSEB",
            "dates": "2013",
            "grade": "67.5%",
            "source_section": "education",
            "source_heading": "Educational Background",
        },
    ]
    assert result["extraction_integrity"]["accepted_counts"] == {
        "education": 3,
        "projects": 0,
        "skills": 0,
    }
    assert len(result["normalized"]["education"]) == 3
    assert result["normalized"]["education"][0]["source_section"] == "education"
    assert result["normalized"]["projects"] == []


def test_explicit_projects_are_retained_but_employment_headings_are_not_projects() -> None:
    text = """
## Work Experience
### Senior Engineer
Example Industries | Jan 2020 - Dec 2023
- Led production operations.

## Selected Projects
### Inventory Forecasting
Forecast demand from historical order data.
Technologies: Python, PostgreSQL
- Reduced stock-outs.
"""

    result = ResumeFieldExtractor.extract(text)

    assert [item["name"] for item in result["projects"]] == ["Inventory Forecasting"]
    assert result["projects"][0]["technologies"] == ["Python", "PostgreSQL"]
    assert result["projects"][0]["source_section"] == "projects"
    assert [item["name"]["normalized_value"] for item in result["normalized"]["projects"]] == [
        "Inventory Forecasting"
    ]


def test_embedded_project_title_uses_label_value_not_previous_employment_line() -> None:
    result = ResumeFieldExtractor.extract(
        """
# Work Experience
## Process Engineer
Project Title: Heat Recovery Optimization
Project Highlights: Reduced steam consumption by 12 percent.
Technologies: DWSIM, Python
"""
    )

    assert [project["name"] for project in result["projects"]] == ["Heat Recovery Optimization"]
    assert result["projects"][0]["source_heading"] == "Embedded Project"


def test_unknown_peer_heading_ends_section_but_nested_role_heading_does_not() -> None:
    detected = ResumeSectionDetector.detect(
        """
## Education
B.E. Chemical | Example University | 2019
## Volunteer Leadership
March 2023
## Work Experience
### Process Engineer
Example Industries | 2020 - Present
""".splitlines()
    )

    assert detected.blocks(SectionKind.EDUCATION)[0].lines == (
        "B.E. Chemical | Example University | 2019",
    )
    assert detected.blocks(SectionKind.UNKNOWN)[0].heading == "Volunteer Leadership"
    assert "### Process Engineer" in detected.blocks(SectionKind.EXPERIENCE)[0].lines


def test_missing_sections_fail_closed_instead_of_scanning_the_whole_resume() -> None:
    text = """
## SAMPLE PERSON
### Profile
Operations specialist.
### Work Experience
### Shift Engineer
Example Ltd | March 2021 - March 2024
- Supervised plant operations.
### Declaration
The information is correct.
"""

    result = ResumeFieldExtractor.extract(text)

    assert result["education"] == []
    assert result["projects"] == []
    assert result["extraction_integrity"]["source_sections_found"] == {
        "education": False,
        "projects": False,
        "skills": False,
    }


def test_malformed_section_content_is_rejected_with_bounded_reason_codes() -> None:
    result = ResumeFieldExtractor.extract(
        """
## Education
Available on request.
## Projects
Confidential client work.
"""
    )

    assert result["education"] == []
    assert result["projects"] == []
    assert result["extraction_integrity"]["rejected_counts"] == {
        "education.INSUFFICIENT_EVIDENCE": 1,
        "projects.INSUFFICIENT_EVIDENCE": 1,
    }


def test_month_march_is_not_normalized_to_architecture_degree() -> None:
    assert ResumeNormalizer._canonical_degree("March 2025 – till date") is None
    assert ResumeNormalizer._canonical_degree("M.Arch") == "M.Arch"
    assert ResumeNormalizer._canonical_degree("Master of Architecture") == "M.Arch"


def test_normalizer_fails_closed_for_scalar_and_malformed_record_collections() -> None:
    normalized = ResumeNormalizer.normalize(
        {
            "education": "B.E. Chemical",
            "projects": {"name": "Not a collection"},
        },
        "",
    )

    assert normalized.education == []
    assert normalized.projects == []


def test_tabular_and_inline_education_records_map_columns_without_cross_mapping() -> None:
    result = ResumeFieldExtractor.extract(
        """
## Academic Qualifications
B.Tech Chemical Engineering    Example Technical University    2020    8.1 CGPA
H.S.C, Example State Board, 2016, 72%
"""
    )

    assert result["education"] == [
        {
            "degree": "B.Tech Chemical Engineering",
            "institution": "Example Technical University",
            "dates": "2020",
            "grade": "8.1 CGPA",
            "source_section": "education",
            "source_heading": "Academic Qualifications",
        },
        {
            "degree": "H.S.C",
            "institution": "Example State Board",
            "dates": "2016",
            "grade": "72%",
            "source_section": "education",
            "source_heading": "Academic Qualifications",
        },
    ]


def test_target_sections_reject_employment_and_person_shaped_records() -> None:
    result = ResumeFieldExtractor.extract(
        """
## Education
B.E. Chemical
Sample Candidate Full Name
## Projects
### Shift Engineer
Example Industries | March 2021 - March 2024
- Supervised production operations.
"""
    )

    assert result["education"] == []
    assert result["projects"] == []
    assert result["extraction_integrity"]["rejected_counts"] == {
        "education.MALFORMED_VALUE": 1,
        "projects.EMPLOYMENT_SHAPED": 1,
    }


def test_existing_experience_alias_and_plain_project_title_remain_supported() -> None:
    result = ResumeFieldExtractor.extract(
        """
## Employment Record
### Process Engineer
Example Industries | 2020 - Present
- Improved yield.
## Project Work
Heat Recovery Optimization
Reduced steam consumption by 12 percent.
Technologies: DWSIM
"""
    )

    assert result["work_experience"]
    assert [project["name"] for project in result["projects"]] == ["Heat Recovery Optimization"]


def test_multiple_plain_projects_split_on_record_boundaries() -> None:
    result = ResumeFieldExtractor.extract(
        """
## Projects
Forecasting Engine
Built a demand forecasting model.

Safety Dashboard
Created operational safety visualizations.
"""
    )

    assert [project["name"] for project in result["projects"]] == [
        "Forecasting Engine",
        "Safety Dashboard",
    ]


def test_blank_after_project_title_does_not_turn_description_into_title() -> None:
    result = ResumeFieldExtractor.extract(
        """
## Projects
### Inventory Forecasting

Built a demand forecasting model.
"""
    )

    assert [project["name"] for project in result["projects"]] == ["Inventory Forecasting"]
    assert result["projects"][0]["description"] == "Built a demand forecasting model."


def test_embedded_project_stops_at_plain_canonical_section_and_bounds_evidence() -> None:
    result = ResumeFieldExtractor.extract(
        "\n".join(
            [
                "Work Experience",
                "Project Title: Heat Recovery Optimization",
                "Project Highlights: Reduced steam consumption.",
                *[f"- Evidence {index}" for index in range(200)],
                "Declaration",
                "The information above is correct.",
            ]
        )
    )

    assert len(result["projects"]) == 1
    assert len(result["projects"][0]["bullet_points"]) == 128
    assert "information above" not in result["projects"][0].get("description", "")


def test_extraction_versions_invalidate_pre_integrity_results() -> None:
    assert settings.EXTRACTION_PARSER_VERSION == "1.2.0"
    assert settings.EXTRACTION_SCHEMA_VERSION == "2.1.0"
