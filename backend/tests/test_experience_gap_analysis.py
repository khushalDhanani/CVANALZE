from __future__ import annotations
import datetime
import pytest
from app.services.experience_gap_service import ExperienceGapService


def test_experience_gap_analysis_dual_fact_education_covered():
    # Candidate with a 7-month employment hiatus covered by Master's Degree education
    resume_json = {
        "work_experience": [
            {
                "job_title": "Junior Developer",
                "company": "Alpha Tech",
                "dates": "01/2020 - 12/2020",
                "employment_type": "full_time",
            },
            {
                "job_title": "Senior Engineer",
                "company": "Beta Corp",
                "dates": "08/2021 - 12/2022",
                "employment_type": "full_time",
            },
        ],
        "education": [
            {
                "degree": "M.Sc Computer Science",
                "dates": "01/2021 - 07/2021",
            }
        ],
    }

    analysis = ExperienceGapService.analyze_timeline(
        resume_json, reference_date=datetime.date(2023, 1, 1), gap_threshold_days=60
    )

    assert analysis.summary.total_employment_gaps_count == 1
    assert analysis.summary.unexplained_gaps_count == 0
    assert len(analysis.detected_gaps) == 1

    gap = analysis.detected_gaps[0]
    assert gap.category == "EMPLOYMENT_GAP"
    assert gap.coverage_status == "EDUCATION_COVERED"
    assert gap.hr_review_indicator is False
    assert "Education Covered" in gap.description or "Education Period" in gap.description


def test_bullet_evidence_without_explicit_year_is_not_parsed():
    """Bullet evidence with no explicit year (e.g. 'RAID-5') must NOT fabricate a
    Jan-2000 start date."""
    start, end, is_current, precision, date_conf = ExperienceGapService._parse_job_dates_strict(
        raw_dates="",
        job={},
        cv_text="IT Executive at BODAL CHEMICALS LTD. Handling system and network administration including RAID-5 storage configuration.",
        company="BODAL CHEMICALS",
        title="IT Executive",
        resps=["Configuring RAID-5 storage", "Network administration"],
        evidence=[],
        ref_date=datetime.date(2026, 8, 7),
    )
    assert start is None
    assert end is None
    assert date_conf == "UNKNOWN"


def test_bullet_evidence_with_explicit_year_is_parsed():
    """Bullet evidence containing a real year range must still be parsed."""
    start, end, is_current, precision, date_conf = ExperienceGapService._parse_job_dates_strict(
        raw_dates="",
        job={},
        cv_text="Worked at ABC Pharma from Oct-2020 to Jul-2024.",
        company="ABC Pharma",
        title="Executive",
        resps=["Managed production from Oct-2020 to Jul-2024"],
        evidence=[],
        ref_date=datetime.date(2026, 8, 7),
    )
    assert start == datetime.date(2020, 1, 1)
    assert end == datetime.date(2024, 12, 31)


def test_experience_gap_analysis_configurable_threshold():
    # Hiatus of 45 days: Under 60-day threshold, ignored. Under 30-day threshold, detected.
    resume_json = {
        "work_experience": [
            {
                "job_title": "Role 1",
                "company": "Company 1",
                "dates": "01/2020 - 05/2020",
                "employment_type": "full_time",
            },
            {
                "job_title": "Role 2",
                "company": "Company 2",
                "dates": "07/2020 - 12/2020",
                "employment_type": "full_time",
            },
        ]
    }

    analysis_60 = ExperienceGapService.analyze_timeline(
        resume_json, reference_date=datetime.date(2021, 1, 1), gap_threshold_days=60
    )
    assert analysis_60.summary.total_employment_gaps_count == 0

    analysis_30 = ExperienceGapService.analyze_timeline(
        resume_json, reference_date=datetime.date(2021, 1, 1), gap_threshold_days=30
    )
    assert analysis_30.summary.total_employment_gaps_count == 1


def test_experience_gap_analysis_date_confidence_and_analysis_confidence():
    # Dates with EXACT vs YEAR_ONLY precision
    resume_json = {
        "work_experience": [
            {
                "job_title": "Engineer",
                "company": "Exact Corp",
                "dates": "15/01/2020 - 30/12/2021",
                "employment_type": "full_time",
            },
            {
                "job_title": "Consultant",
                "company": "Vague Inc",
                "dates": "2022 - 2023",
                "employment_type": "consulting",
            },
        ]
    }

    analysis = ExperienceGapService.analyze_timeline(
        resume_json, reference_date=datetime.date(2024, 1, 1)
    )

    nodes = analysis.timeline_nodes
    assert nodes[0].date_confidence == "EXACT"
    assert nodes[1].date_confidence == "YEAR_ONLY"
    assert 0.0 < analysis.summary.analysis_confidence <= 1.0


def test_experience_gap_analysis_interval_union_experience():
    # Overlapping roles running simultaneously should NOT double-count experience
    resume_json = {
        "work_experience": [
            {
                "job_title": "Full-Time Engineer",
                "company": "Main Corp",
                "dates": "01/2020 - 12/2021",  # 2 years
                "employment_type": "full_time",
            },
            {
                "job_title": "Part-Time Advisor",
                "company": "Side LLC",
                "dates": "06/2020 - 06/2021",  # 1 year concurrent
                "employment_type": "part_time",
            },
        ]
    }

    analysis = ExperienceGapService.analyze_timeline(
        resume_json, reference_date=datetime.date(2022, 1, 1)
    )

    assert analysis.summary.concurrent_roles_count >= 1
    assert round(analysis.summary.total_verified_years, 1) == 2.0


def test_experience_gap_analysis_chaitanya_profile_clustering():
    # Profile with overlapping roles and undated header entry
    resume_json = {
        "work_experience": [
            {
                "job_title": "Position",
                "company": "Reliance Industries Ltd",
                "dates": "N/A",  # Undated company header without responsibilities -> filtered in Stage 1
            },
            {
                "job_title": "Sr. Executive",
                "company": "Reliance Industries Ltd",
                "dates": "05/2023 - 10/2023",
            },
            {
                "job_title": "QA Operations",
                "company": "Reliance Industries Ltd - Quality Assurance Operations",
                "dates": "10/2023 - Present",
            },
            {
                "job_title": "Inspector",
                "company": "REC Solar Deputation",
                "dates": "05/2023 - Present",
            },
        ]
    }

    analysis = ExperienceGapService.analyze_timeline(
        resume_json, reference_date=datetime.date(2024, 1, 1)
    )

    # 1. Pure placeholder header without dates/responsibilities is purged in Stage 1
    assert len(analysis.undated_nodes) == 0

    # 2. Roles under Reliance parent entity are grouped into CanonicalJobs
    assert len(analysis.canonical_jobs) >= 1
    assert analysis.canonical_jobs[0].parent_company == "Reliance Industries Ltd"



def test_experience_gap_analysis_chaitanya_zero_gaps():
    # Torrent Power (Oct 2020 - Apr 2023) -> Reliance (May 2023 - Present) continuous transition
    resume_json = {
        "work_experience": [
            {
                "job_title": "Junior Executive",
                "company": "Torrent Power Ltd",
                "responsibilities": ["October 2020 - April 2023"],
            },
            {
                "job_title": "Sr. Executive",
                "company": "Reliance Industries Ltd",
                "dates": "May 2023 - Oct 2023",
                "responsibilities": ["Includes international deputation to REC Solar Pte. Ltd., Singapore"],
            },
            {
                "job_title": "QA Operations",
                "company": "Reliance Industries Ltd",
                "dates": "Oct 2023 - Present",
            },
        ]
    }

    cv_text = """
    Torrent Power Ltd
    Junior Executive - Field Operations & Quality
    October 2020 - April 2023

    Reliance Industries Ltd
    May 2023 - Present
    """

    analysis = ExperienceGapService.analyze_timeline(
        resume_json, cv_text=cv_text, reference_date=datetime.date(2024, 1, 1)
    )

    # Must result in ZERO detected employment gaps, 0 concurrent roles, and correct total experience
    assert analysis.summary.total_employment_gaps_count == 0
    assert analysis.summary.unexplained_gaps_count == 0
    assert analysis.summary.concurrent_roles_count == 0
    assert len(analysis.detected_gaps) == 0
    assert analysis.summary.total_verified_years == 3.3  # Oct 2020 to Jan 2024 (3.25 -> 3.3)


def test_continuous_job_transitions():
    # Job A ends Apr 2023, Job B starts May 2023 (Adjacent month transition -> 0 gaps)
    resume_json = {
        "work_experience": [
            {"job_title": "Engineer", "company": "Company A", "dates": "01/2021 - 04/2023"},
            {"job_title": "Lead Engineer", "company": "Company B", "dates": "05/2023 - 12/2024"},
        ]
    }
    analysis = ExperienceGapService.analyze_timeline(resume_json, reference_date=datetime.date(2025, 1, 1))
    assert analysis.summary.total_employment_gaps_count == 0


def test_overlapping_employment():
    # Full-time role + Part-time consulting running concurrently -> 0 gaps
    resume_json = {
        "work_experience": [
            {"job_title": "Full-Time Dev", "company": "Tech Corp", "dates": "01/2022 - 12/2023"},
            {"job_title": "Part-Time Advisor", "company": "Startup LLC", "dates": "06/2022 - 06/2023"},
        ]
    }
    analysis = ExperienceGapService.analyze_timeline(resume_json, reference_date=datetime.date(2024, 1, 1))
    assert analysis.summary.total_employment_gaps_count == 0
    assert analysis.summary.concurrent_roles_count >= 1


def test_deputation_and_internal_assignments():
    # International deputation posting under parent company -> 0 gaps
    resume_json = {
        "work_experience": [
            {"job_title": "Sr. Executive", "company": "Parent Global", "dates": "01/2021 - Present"},
            {
                "job_title": "Quality Inspector",
                "company": "Overseas Sub Pte Ltd",
                "dates": "03/2022 - 09/2022",
                "responsibilities": ["International deputation assignment by Parent Global"],
            },
        ]
    }
    analysis = ExperienceGapService.analyze_timeline(resume_json, reference_date=datetime.date(2024, 1, 1))
    assert analysis.summary.total_employment_gaps_count == 0


def test_promotions_and_transfers():
    # Promotion & transfer within same company -> 0 gaps
    resume_json = {
        "work_experience": [
            {"job_title": "Junior Analyst", "company": "Finance Inc", "dates": "01/2020 - 12/2021"},
            {"job_title": "Senior Analyst (Internal Transfer)", "company": "Finance Inc", "dates": "01/2022 - 12/2023"},
        ]
    }
    analysis = ExperienceGapService.analyze_timeline(resume_json, reference_date=datetime.date(2024, 1, 1))
    assert analysis.summary.total_employment_gaps_count == 0


def test_freelance_and_concurrent_work():
    # Freelance project during employment hiatus -> FREELANCE_COVERED
    resume_json = {
        "work_experience": [
            {"job_title": "Full-Time Dev", "company": "Corp A", "dates": "01/2020 - 12/2020", "employment_type": "full_time"},
            {"job_title": "Freelance Consultant", "company": "Self", "dates": "02/2021 - 07/2021", "employment_type": "freelance"},
            {"job_title": "Senior Dev", "company": "Corp B", "dates": "08/2021 - 12/2022", "employment_type": "full_time"},
        ]
    }
    analysis = ExperienceGapService.analyze_timeline(resume_json, reference_date=datetime.date(2023, 1, 1))
    assert analysis.summary.unexplained_gaps_count == 0


def test_explicit_7type_entity_resolution():
    resume_json = {
        "work_experience": [
            {"job_title": "Position", "company": "Organization", "dates": "N/A"},  # INVALID_HEADING
            {"job_title": "Software Engineer", "company": "TechCorp Global", "dates": "01/2020 - 12/2022"},  # PARENT_EMPLOYMENT
            {"job_title": "Senior Engineer (Promotion)", "company": "TechCorp Global", "dates": "01/2022 - 12/2022", "responsibilities": ["Internal promotion"]},  # PROMOTION_TRANSFER
            {"job_title": "Project Lead (Deputation)", "company": "Client Corp", "dates": "06/2021 - 12/2021", "responsibilities": ["International deputation assignment by TechCorp Global"]},  # DEPUTATION
        ]
    }
    analysis = ExperienceGapService.analyze_timeline(resume_json, reference_date=datetime.date(2023, 1, 1))

    # INVALID_HEADING purged
    assert len(analysis.canonical_jobs) == 1
    c_job = analysis.canonical_jobs[0]
    assert c_job.parent_company == "TechCorp Global"
    assert c_job.entity_resolution == "PARENT_EMPLOYMENT"

    # Child assignments resolution verified
    asg_resolutions = [asg.entity_resolution for asg in c_job.child_assignments]
    assert "DEPUTATION" in asg_resolutions
    assert "PROMOTION_TRANSFER" in asg_resolutions




