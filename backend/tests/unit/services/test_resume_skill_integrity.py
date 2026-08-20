from __future__ import annotations

from app.services.resume_field_extractor import ResumeFieldExtractor


def test_professional_skills_are_extracted_from_their_canonical_section() -> None:
    result = ResumeFieldExtractor.extract(
        """
## Work Experience
### Process Engineer
Example Industries | March 2021 - March 2024
- Managed production operations.

## Professional Skills
- DCS Operations
- HAZOP
- Process Optimization

## Personal Details
- Nationality: Indian
"""
    )

    assert result["skills"] == {
        "categorized": {},
        "all_skills": ["DCS Operations", "HAZOP", "Process Optimization"],
    }
    assert result["extraction_integrity"]["accepted_counts"]["skills"] == 3
    assert result["extraction_integrity"]["source_sections_found"]["skills"] is True


def test_missing_skills_section_does_not_promote_capitalized_cv_text_to_skills() -> None:
    result = ResumeFieldExtractor.extract(
        """
## Work Experience
### Process Engineer
Example Industries | March 2021 - March 2024
- Managed Distributed Control System operations and Safety Compliance.
- Coordinated Production Planning with Shift Supervisors.

## Personal Details
Name: Sample Candidate
Address: Example City
Nationality: Indian
"""
    )

    assert result["skills"] == {"categorized": {}, "all_skills": []}
    assert result["extraction_integrity"]["accepted_counts"]["skills"] == 0
    assert result["extraction_integrity"]["source_sections_found"]["skills"] is False


def test_empty_skills_section_does_not_absorb_following_personal_details() -> None:
    result = ResumeFieldExtractor.extract(
        """
## Skills
## Personal Details
- Team Building
- Nationality: Indian
- Address: Example City
"""
    )

    assert result["skills"] == {"categorized": {}, "all_skills": []}
    assert "Recovered Context Skills" not in result["skills"]["categorized"]


def test_contact_or_employment_fields_inside_skills_are_rejected_without_losing_valid_skills() -> None:
    result = ResumeFieldExtractor.extract(
        """
## Skills
- Python
- Address: Example City
- Email: sample@example.com
- Duration: March 2021 - March 2024
- Managed production operations
- Process Engineer
- Senior Software Engineer II
- Process Engineer (Contract)
- Lead Developer - Backend
- Software Engineer – Backend
- PostgreSQL
- Email Marketing
- Address Verification
- @angular/core
- Operator Training
- Executive Coaching
"""
    )

    assert result["skills"]["all_skills"] == [
        "Python",
        "PostgreSQL",
        "Email Marketing",
        "Address Verification",
        "@angular/core",
        "Operator Training",
        "Executive Coaching",
    ]
    assert result["extraction_integrity"]["rejected_counts"] == {
        "skills.CONTACT_SHAPED": 2,
        "skills.EMPLOYMENT_SHAPED": 6,
        "skills.WRONG_SECTION": 1,
    }


def test_skill_collection_is_bounded_for_oversized_sections() -> None:
    result = ResumeFieldExtractor.extract(
        "## Skills\n" + "\n".join(f"- Capability {index}" for index in range(400))
    )

    assert len(result["skills"]["all_skills"]) == 256
    assert result["extraction_integrity"]["rejected_counts"]["skills.LIMIT_EXCEEDED"] >= 1


def test_plain_computer_proficiency_heading_is_supported_without_candidate_specific_rules() -> None:
    result = ResumeFieldExtractor.extract(
        """
Computer Proficiency
SAP, LIMS, Microsoft Excel
Education
B.Sc Chemistry
Example University
2020
"""
    )

    assert result["skills"]["all_skills"] == ["SAP", "LIMS", "Microsoft Excel"]
