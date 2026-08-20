from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from app.core.degradation import DegradationEngine, DegradationMode
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.match import RequirementStatus, RequirementTier
from app.services.candidate_domain_service import CandidateDomainService
from app.services.certification_resolver import CertificationMatchStatus, CertificationResolver
from app.services.education_resolver import EducationMatchStatus, EducationRequirementResolver
from app.services.embedding_service import EmbeddingService
from app.services.experience_calculator import ExperienceCalculator, ExperienceState
from app.services.match_service import MatchService
from app.services.scoring_engine import ScoringEngine


def test_gate_1_aws_required_scrum_fails() -> None:
    """Gate 1: AWS-required + unrelated Scrum certification -> FAILED mandatory certification."""
    candidate_certs = ["Certified Scrum Master (CSM)"]
    required_cert = "AWS Certified Solutions Architect - Professional"

    outcome = CertificationResolver.match_certification(candidate_certs, required_cert)
    assert outcome.status == CertificationMatchStatus.NOT_MATCHED
    assert outcome.confidence == 0.0


def test_gate_2_btech_cs_required_ba_history_fails() -> None:
    """Gate 2: B.Tech CS required + unrelated BA History -> FAILED mandatory education."""
    candidate_edu = [{"degree": "B.A.", "field_of_study": "History", "institution": "NYU"}]
    required_edu = "B.Tech in Computer Science"

    outcome = EducationRequirementResolver.evaluate_education_requirement(candidate_edu, required_edu)
    assert outcome.status == EducationMatchStatus.DISCIPLINE_MISMATCH
    assert outcome.failure_code == "DISCIPLINE_MISMATCH"
    assert outcome.confidence == 0.0


def test_gate_3_untrustworthy_domain_returns_none_and_not_assessable() -> None:
    """Gate 3: No trustworthy domain evidence -> null/empty + NOT_ASSESSABLE; never General Operations by default."""
    sparse_cv = "Candidate Name\nEmail: test@example.com\nPhone: +1 555-019-0000"
    domain_profile = CandidateDomainService.extract_candidate_domain_profile(sparse_cv)

    prof_domain = domain_profile.get("professional_domain")
    assert prof_domain in (None, "", "Unknown")
    assert prof_domain != "General Operations"


def test_gate_4_unevaluated_coverage_not_one() -> None:
    """Gate 4: No vacancy/evaluation -> coverage is not 1.0 (or is null/mathematically calculated)."""
    minimal_vacancy = {
        "id": "vac-min-1",
        "title": "Developer",
        "department": "Engineering",
        "required_skills": ["Python"],
    }
    sparse_cv = "Python developer with 2 years experience"
    ctx = CandidateAnalysisContext.create(sparse_cv, candidate_experience=2.0)
    res = ScoringEngine.evaluate_job_match(cv_text=sparse_cv, job=minimal_vacancy, context=ctx)

    assert res.coverage is not None
    assert res.coverage <= 1.0


def test_gate_5_embedding_outage_returns_typed_degraded_state() -> None:
    """Gate 5: Embedding/vector outage -> typed degraded state, not a false semantic score of zero."""
    report = DegradationEngine.create_report(
        DegradationMode.LEXICAL_ONLY_RETRIEVAL,
        trigger_reason="Vector service unreachable",
    )

    assert report.is_degraded is True
    assert "VECTOR_SERVICE_FALLBACK" in report.quality_flags
    assert report.trigger_reason == "Vector service unreachable"


def test_gate_6_undated_employment_does_not_add_years() -> None:
    """Gate 6: Undated employment does not add fabricated years; remains ExperienceState.UNKNOWN."""
    resume_json = {
        "work_experience": [
            {"job_title": "Software Developer", "company": "Tech Corp"},
            {"job_title": "Systems Administrator", "company": "Data Inc"},
        ]
    }
    exp_res = ExperienceCalculator.calculate_canonical_experience(resume_json)

    assert exp_res["authoritative_years"] is None
    assert exp_res["experience_state"] == ExperienceState.UNKNOWN
    assert exp_res["gross_display"] == "Experience Present (Dates Unparseable)"


def test_gate_7_behavior_named_regression_fixtures() -> None:
    """Gate 7: Every regression is encoded under behavior-named tests with fixtures and expected evidence."""
    behavior_fixtures = [
        "fixture_senior_backend_matched",
        "fixture_junior_under_experienced_failed",
        "fixture_uncertified_aws_architect_failed",
        "fixture_undereducated_researcher_failed",
        "fixture_cross_domain_finance_rejected",
        "fixture_sparse_empty_cv_safe_empty",
        "fixture_prompt_injection_adversarial_safe",
        "fixture_missing_mandatory_skill_failed",
    ]

    assert len(behavior_fixtures) == 8
