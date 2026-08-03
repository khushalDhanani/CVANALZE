from app.schemas.candidate_context import CandidateAnalysisContext
from app.services.job_taxonomy import TaxonomyClassifier
from app.services.match_evaluators import (
    CareerTransitionEvaluator,
    RecommendationEvaluator,
    RequirementEvaluator,
)
from app.services.scoring_engine import ScoringEngine


def test_candidate_analysis_context_creation():
    cv_text = """
    John Doe
    Email: john@example.com
    Current Role: Senior Python Developer
    Skills: Python, FastAPI, PostgreSQL, Docker, Redis
    Experience: 5 years in software engineering.
    Education: B.Tech Computer Science
    """

    context = CandidateAnalysisContext.create(cv_text=cv_text, candidate_experience=5.0)

    assert context.cv_text == cv_text
    assert "python" in context.norm_text
    assert context.current_role == "Senior Python Developer"
    assert context.candidate_experience == 5.0
    assert "IT & Software Services" in context.cand_tax_domain
    assert context.is_software_cand is True
    assert context.cand_primary_family is not None


def test_taxonomy_classifier_caching():
    cv_text = "Software Developer with React, Node.js, and TypeScript skills."

    d1, f1 = TaxonomyClassifier.classify_candidate(cv_text)
    d2, f2 = TaxonomyClassifier.classify_candidate(cv_text)

    assert d1 == d2
    assert f1 == f2


def test_scoring_engine_parity_with_context():
    cv_text = """
    Jane Smith
    Current Role: Maintenance Engineer
    Skills: Mechanical maintenance, PLC, pumps, valves, EHS
    Experience: 4 years
    Education: B.E. Mechanical Engineering
    """
    job = {
        "id": "vac_101",
        "title": "Maintenance Engineer",
        "department": "Plant Maintenance",
        "required_skills": ["Mechanical maintenance", "PLC"],
        "min_experience_years": 3.0,
    }

    # Evaluate without explicit context (context created inside)
    res_direct = ScoringEngine.evaluate_job_match(cv_text, job, candidate_experience=4.0)

    # Evaluate with pre-computed context
    ctx = CandidateAnalysisContext.create(cv_text, candidate_experience=4.0)
    res_context = ScoringEngine.evaluate_job_match(cv_text, job, context=ctx)

    assert res_direct.score == res_context.score
    assert res_direct.classification == res_context.classification
    assert res_direct.role_score == res_context.role_score
    assert res_direct.skills_score == res_context.skills_score
    assert res_direct.candidate_job_family == res_context.candidate_job_family


def test_match_evaluators_direct():
    cv_text = "Python developer with FastAPI experience."
    ctx = CandidateAnalysisContext.create(cv_text)
    job = {
        "title": "Python Developer",
        "department": "IT",
        "required_skills": ["Python", "FastAPI"],
    }

    req_results = RequirementEvaluator.evaluate(
        context=ctx,
        job=job,
        llm_match=None,
        penalty_per_item=15.0,
        extract_term_matches_fn=ScoringEngine._extract_term_matches,
    )
    assert len(req_results.matched_skills) == 2
    assert len(req_results.mandatory_failures) == 0

    transition_detected, _note, _common = CareerTransitionEvaluator.evaluate(
        context=ctx,
        job=job,
        llm_match=None,
    )
    assert transition_detected is False

    rec_results = RecommendationEvaluator.evaluate(
        final_score=85.0,
        coverage=1.0,
        total_req_count=2,
        evidence_count=2,
        match_high_threshold=80.0,
        match_medium_threshold=50.0,
        reason_str="Match clean",
        missing_criteria=[],
    )
    assert rec_results.classification == "HIGH"
    assert "Strong candidate" in rec_results.recommendation
