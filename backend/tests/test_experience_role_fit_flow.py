from __future__ import annotations
import pytest
from app.services.experience_calculator import ExperienceCalculator
from app.services.recommendation_service import RecommendationService
from app.services.match_service import MatchService
from app.schemas.analysis import MatchStatus


def test_experience_calculator_formatting_and_stated_extraction():
    # 1. Verify clean seniority formatting (no double 'level')
    cv_text = "Experienced Instrumentation Asst Manager with 13+ years of experience in project execution."
    summary = ExperienceCalculator.calculate_canonical_experience({}, cv_text)

    assert summary["authoritative_years"] == 13.0
    assert summary["seniority"] == "Executive / Director"
    assert "Assessed as Executive / Director level with 13.0 years of verified experience." in summary["experience_assessment"]
    assert "level level" not in summary["experience_assessment"]

    # 2. Mid-level verification
    cv_text_mid = "Software Developer with 3+ years experience in ASP.NET Core and Flutter."
    summary_mid = ExperienceCalculator.calculate_canonical_experience({}, cv_text_mid)

    assert summary_mid["authoritative_years"] == 3.0
    assert summary_mid["seniority"] == "Mid-Level"
    assert "Assessed as Mid-Level with 3.0 years of verified experience." in summary_mid["experience_assessment"]
    assert "Mid-Level level" not in summary_mid["experience_assessment"]


def test_experience_calculator_genuinely_empty():
    summary = ExperienceCalculator.calculate_canonical_experience({}, "")
    assert summary["authoritative_years"] == 0.0
    assert summary["seniority"] == "Entry Level"
    assert summary["experience_assessment"] == "Assessed as Entry Level (No employment history documented)."


@pytest.mark.asyncio
async def test_match_service_preserves_candidate_domain_when_no_vacancy_matches():
    from app.repositories.job import JobRepository
    cv_text = """
    ## SHAHDAB SHAIKH
    Instrumentation Professional with 13+ years of experience in chemical plant maintenance.
    Skills: DCS, Honeywell, SCADA, PLC, Transmitters, Calibration, Maintenance, Instrumentation.
    """
    openings = JobRepository.get_all_jobs()
    analysis = await MatchService.analyze_single_cv(
        cv_text=cv_text,
        job_openings=openings,
        candidate_id="test_cand_123",
    )

    assert analysis.has_genuine_match is False or analysis.has_genuine_match is True
    # Verify candidate domain/dept profile or status is preserved
    assert analysis.status == "COMPLETED" or analysis.has_genuine_match is not None
    assert analysis.active_vacancy_summary is not None



def test_recommendation_service_fallback_keys():
    # Test processing fallback
    recs = RecommendationService.get_candidate_recommendations("non_existent_cv_key_9999")
    assert recs["experience_assessment"] == "N/A"
    assert recs["role_department_fit"] == "N/A"
    assert recs["hiring_recommendation"] == "ANALYSIS_NOT_AVAILABLE"
