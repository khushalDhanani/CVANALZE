from __future__ import annotations
from datetime import datetime
import pytest

from app.services.date_interval_parser import DateIntervalParser
from app.services.experience_calculator import ExperienceCalculator, ExperienceState
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.resume_normalizer import ResumeNormalizer


def test_1_uploaded_cv_fixture_never_returns_zero():
    """
    Test the exact failing uploaded CV scenario:
    - Jan 2019 to Apr 2020 (Job 1: 16 months)
    - May 2020 to Present (Job 2: ~75 months as of 2026)
    - Explicit claim: 'Work experience (6+ Years)'
    Must resolve as CALCULATED with ~7.5 years (~90 months) and NEVER 0 years 0 months.
    """
    cv_text = """
    # John Doe
    Email: john.doe@example.com
    Phone: +1-555-0199
    
    ## SUMMARY
    Senior Software Engineer with extensive backend experience.
    Work experience (6+ Years)
    
    ## WORK EXPERIENCE
    Tech Mahindra
    Software Engineer
    Jan 2019 to Apr 2020
    - Developed microservices in Python and FastAPI.
    
    Google India
    Senior Software Engineer
    May 2020 to Present
    - Leading cloud infrastructure and distributed data pipelines.
    
    ## EDUCATION
    Bachelor of Technology in Computer Science
    2014 - 2018
    """
    
    extracted = ResumeFieldExtractor.extract(cv_text)
    assert len(extracted["work_experience"]) >= 2
    
    # Calculate canonical experience
    ref_date = datetime(2026, 8, 8)
    summary = ExperienceCalculator.calculate_canonical_experience(extracted, cv_text, reference_date=ref_date)
    
    assert summary["experience_state"] == ExperienceState.CALCULATED
    assert summary["experience_years"] is not None
    assert summary["experience_years"] >= 7.0
    assert summary["gross_display"] != "0 years 0 months"
    assert "years" in summary["gross_display"]


def test_2_en_dash_and_em_dash_date_ranges():
    """
    Test en-dash (U+2013), em-dash (U+2014), and unspaced hyphens.
    """
    ref_date = datetime(2026, 1, 1)
    
    # En-dash: Jan 2019 – Apr 2020
    inv1 = DateIntervalParser.parse_interval("Jan 2019 – Apr 2020", ref_date=ref_date)
    assert inv1.start_date == "2019-01-01"
    assert inv1.end_date == "2020-04-30"
    assert inv1.duration_months == 16
    
    # Em-dash: May 2020 — Dec 2022
    inv2 = DateIntervalParser.parse_interval("May 2020 — Dec 2022", ref_date=ref_date)
    assert inv2.start_date == "2020-05-01"
    assert inv2.end_date == "2022-12-31"
    assert inv2.duration_months == 32
    
    # Unspaced hyphen: 01/2019-04/2020
    inv3 = DateIntervalParser.parse_interval("01/2019-04/2020", ref_date=ref_date)
    assert inv3.start_date == "2019-01-01"
    assert inv3.end_date == "2020-04-30"


def test_3_to_present_and_dynamic_current_resolution():
    """
    Test 'May 2020 to Present', 'Current', 'Till Date', 'Ongoing'.
    """
    ref_date = datetime(2026, 6, 1)
    
    for present_str in ["May 2020 to Present", "May 2020 - Current", "May 2020 to Till Date", "May 2020 - Ongoing"]:
        inv = DateIntervalParser.parse_interval(present_str, ref_date=ref_date)
        assert inv.is_current is True
        assert inv.start_date == "2020-05-01"
        assert inv.duration_months is not None
        assert inv.duration_months >= 72  # ~6 years


def test_4_same_line_role_company_dates():
    """
    Test single line containing role, company, and date range.
    """
    cv_text = """
    ## Experience
    Senior Software Engineer at Amazon Web Services (Jan 2019 - Apr 2021)
    - Built scalable distributed backend services.
    
    Tech Lead at Microsoft (May 2021 - Present)
    - Architected multi-tenant cloud storage.
    """
    extracted = ResumeFieldExtractor.extract(cv_text)
    ref_date = datetime(2026, 1, 1)
    summary = ExperienceCalculator.calculate_canonical_experience(extracted, cv_text, reference_date=ref_date)
    
    assert summary["experience_state"] == ExperienceState.CALCULATED
    assert summary["experience_years"] is not None
    assert summary["experience_years"] >= 6.8


def test_5_multi_line_employment_formatting():
    """
    Test multi-line format where company is line 1, role is line 2, dates on line 3.
    """
    cv_text = """
    ## Professional Experience
    Bodal Chemicals Ltd
    Instrumentation Assistant Manager
    Jan 2015 to Dec 2019
    • Supervised plant automation and PLC calibration.
    
    Saykha Speciality Chemical Complex
    Manager - Electrical & Instrumentation
    Jan 2020 to Present
    • Lead industrial instrumentation operations.
    """
    extracted = ResumeFieldExtractor.extract(cv_text)
    ref_date = datetime(2026, 1, 1)
    summary = ExperienceCalculator.calculate_canonical_experience(extracted, cv_text, reference_date=ref_date)
    
    assert summary["experience_state"] == ExperienceState.CALCULATED
    assert summary["experience_years"] >= 10.0


def test_6_overlapping_and_concurrent_jobs_merged_without_double_counting():
    """
    Test concurrent jobs (e.g. consulting + full time across 2020-2022) are merged via interval union.
    """
    resume_json = {
        "work_experience": [
            {
                "company": "Company A",
                "job_title": "Software Developer",
                "dates": "Jan 2020 - Dec 2022",  # 36 months
            },
            {
                "company": "Company B",
                "job_title": "Consultant",
                "dates": "Jun 2020 - Jun 2022",  # Overlapping within Company A period
            },
        ]
    }
    
    summary = ExperienceCalculator.calculate_canonical_experience(resume_json)
    assert summary["experience_state"] == ExperienceState.CALCULATED
    # Total unique duration should be 3.0 years (36 months), not double-counted to 5.0 years
    assert summary["experience_years"] == 3.0
    assert summary["total_experience_months"] == 36


def test_7_year_only_date_ranges():
    """
    Test year-only dates: '2018 - 2020', '2020 - 2023'.
    """
    resume_json = {
        "work_experience": [
            {
                "company": "Global Pharma",
                "job_title": "Quality Analyst",
                "dates": "2018 - 2020",
            },
            {
                "company": "Sun Pharmaceuticals",
                "job_title": "QC Executive",
                "dates": "2020 - 2023",
            },
        ]
    }
    
    summary = ExperienceCalculator.calculate_canonical_experience(resume_json)
    assert summary["experience_state"] == ExperienceState.CALCULATED
    assert summary["experience_years"] >= 4.0


def test_8_explicit_claim_fallback_when_dates_unparseable():
    """
    Test explicit CV claim 'Work experience (6+ Years)' when structured dates are missing.
    Must return state CLAIMED with 6.0 years, NEVER 0 years 0 months.
    """
    cv_text = """
    # Jane Doe
    Email: jane.doe@example.com
    
    Work experience (6+ Years)
    
    ## Professional Exposure
    XYZ Industries
    Senior Production Chemist
    - Executed synthesis and quality monitoring.
    """
    
    extracted = ResumeFieldExtractor.extract(cv_text)
    summary = ExperienceCalculator.calculate_canonical_experience(extracted, cv_text)
    
    assert summary["experience_state"] == ExperienceState.CLAIMED
    assert summary["experience_years"] == 6.0
    assert summary["total_experience_months"] == 72
    assert "Claimed" in summary["gross_display"] or "6 years" in summary["gross_display"]


def test_9_unparseable_dates_with_documented_roles_returns_unknown():
    """
    Non-Negotiable Rule:
    When employment history exists but dates are unparseable and no claim was stated,
    the system must return state UNKNOWN and NEVER silently return 0.0 or 0 years 0 months.
    """
    resume_json = {
        "work_experience": [
            {
                "company": "Acme Corp",
                "job_title": "Developer",
                "dates": "N/A",
            },
            {
                "company": "Beta LLC",
                "job_title": "Engineer",
                "dates": "unspecified dates",
            },
        ]
    }
    
    summary = ExperienceCalculator.calculate_canonical_experience(resume_json, cv_text="")
    
    assert summary["experience_state"] == ExperienceState.UNKNOWN
    assert summary["experience_years"] is None
    assert summary["gross_display"] == "Experience Present (Dates Unparseable)"
    assert summary["gross_display"] != "0 years 0 months"


def test_10_fresher_true_zero_experience_returns_zero_confirmed():
    """
    Non-Negotiable Rule:
    0 months must ONLY mean confidently confirmed zero professional experience (fresher).
    """
    cv_text = """
    # Alex Smith
    Email: alex.smith@example.com
    
    ## EDUCATION
    Bachelor of Science in Chemistry
    2021 - 2025
    
    ## PROJECTS
    Synthesis of organic compounds in university laboratory.
    
    ## SKILLS
    HPLC, Titration, Gas Chromatography
    """
    
    extracted = ResumeFieldExtractor.extract(cv_text)
    summary = ExperienceCalculator.calculate_canonical_experience(extracted, cv_text)
    
    assert summary["experience_state"] == ExperienceState.ZERO_CONFIRMED
    assert summary["experience_years"] == 0.0
    assert summary["total_experience_months"] == 0
    assert summary["gross_display"] == "0 years 0 months"


def test_11_continuous_employment_across_multiple_companies():
    """
    Test 3 continuous jobs with no gaps:
    - 2018-01-01 to 2019-12-31 (24 months)
    - 2020-01-01 to 2021-12-31 (24 months)
    - 2022-01-01 to 2023-12-31 (24 months)
    Total = 72 months = 6.0 years.
    """
    resume_json = {
        "work_experience": [
            {"company": "Comp 1", "job_title": "Junior Dev", "dates": "01/2018 - 12/2019"},
            {"company": "Comp 2", "job_title": "Mid Dev", "dates": "01/2020 - 12/2021"},
            {"company": "Comp 3", "job_title": "Senior Dev", "dates": "01/2022 - 12/2023"},
        ]
    }
    
    summary = ExperienceCalculator.calculate_canonical_experience(resume_json)
    assert summary["experience_state"] == ExperienceState.CALCULATED
    assert summary["experience_years"] == 6.0
    assert summary["total_experience_months"] == 72


def test_12_plain_text_section_headings_without_markdown():
    """
    Test CV with plain text uppercase headers (e.g. WORK EXPERIENCE without # or **).
    """
    cv_text = """
    Candidate Name: Tarun Gupta
    Email: tarun.gupta@example.com
    
    WORK EXPERIENCE
    Infosys Technologies
    Systems Engineer
    06/2019 - 10/2021
    
    Tata Consultancy Services
    Senior Systems Engineer
    11/2021 to Present
    
    EDUCATION
    B.E. in Electronics
    """
    
    extracted = ResumeFieldExtractor.extract(cv_text)
    assert len(extracted["work_experience"]) >= 2
    
    ref_date = datetime(2026, 1, 1)
    summary = ExperienceCalculator.calculate_canonical_experience(extracted, cv_text, reference_date=ref_date)
    assert summary["experience_state"] == ExperienceState.CALCULATED
    assert summary["experience_years"] >= 6.0
