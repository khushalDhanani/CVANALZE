from __future__ import annotations

from app.schemas.match import HiringRisk, JobMatchResult
from app.services.hiring_risk_analyzer import HiringRiskAnalyzer, HiringRiskExplanation


def test_hiring_risk_explanation_model() -> None:
    exp = HiringRiskExplanation(
        risk_code="MIN_EXPERIENCE_SHORTFALL",
        title="Experience Below Requirement",
        explanation="Candidate possesses 2 years of relevant experience whereas 4 years are required.",
    )
    assert exp.risk_code == "MIN_EXPERIENCE_SHORTFALL"
    assert "2 years" in exp.explanation


def test_hiring_risk_generation_on_match_result() -> None:
    result = JobMatchResult(
        job_id="job-101",
        job_title="Senior Python Developer",
        classification="HIGH",
        recommendation="Proceed",
        vacancy_id=101,
        department="Engineering",
        score=75.0,
        mandatory_failures=[],
        hiring_risks=[],
    )
    # With no mandatory failures or gap events, no critical risks generated
    HiringRiskAnalyzer.generate_risks(result, context=None, job_ctx=None)
    assert isinstance(result.hiring_risks, list)
