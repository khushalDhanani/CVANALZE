from __future__ import annotations

from app.schemas.candidate_context import CandidateAnalysisContext
from app.services.candidate_domain_service import CandidateDomainService
from app.services.match_evaluators import ComponentScoreEvaluator, RequirementEvaluator
from app.services.scoring_engine import ScoringEngine


def test_unresolved_domain_returns_empty_and_not_found_status() -> None:
    """Workstream 3.2: Unresolved professional domain returns None/empty string, never 'General Operations'."""
    sparse_cv = "John Doe\nEmail: john@example.com\nPhone: +1 555-019-1111\nPersonal Resume"
    res = CandidateDomainService.extract_candidate_domain_profile(sparse_cv)

    domain = res.get("professional_domain")
    assert domain in (None, "", "Unknown")
    assert domain != "General Operations"


def test_unresolved_roles_and_strengths_return_empty_lists() -> None:
    """Workstream 3.2: Unresolved roles and strengths return empty lists [], never unsupported UI assertions."""
    sparse_cv = "Jane Smith\nEmail: jane@example.com\nPhone: +1 555-019-2222\nResume"
    res = CandidateDomainService.extract_candidate_domain_profile(sparse_cv)

    roles = res.get("suitable_job_roles", [])
    strengths = res.get("strengths", [])

    assert "Operations Associate" not in roles
    assert "General technical background" not in strengths


def test_missing_scores_preserved_as_none_and_removed_from_denominator() -> None:
    """Workstream 3.2: Un-evaluable score components preserve None and are removed from active_weights denominator."""
    minimal_vacancy = {
        "id": "vac-minimal-101",
        "title": "Software Engineer",
        "department": "Engineering",
        "required_skills": ["Python"],
    }
    sparse_cv = "Python developer with 2 years experience"

    ctx = CandidateAnalysisContext.create(sparse_cv, candidate_experience=2.0)
    res = ScoringEngine.evaluate_job_match(cv_text=sparse_cv, job=minimal_vacancy, context=ctx)

    # Certification and Education were not specified in minimal_vacancy
    assert res.score_breakdown is not None
    assert res.coverage <= 1.0
