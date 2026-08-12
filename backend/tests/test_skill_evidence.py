import pytest
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.services.match_evaluators import RequirementEvaluator
from app.schemas.scoring_config import ScoringConfig
from app.services.scoring_engine import ScoringEngine
from app.schemas.analysis import OptimizedCandidateProfile

def test_cv_missing_skill_inferred_llm():
    # CV missing required skill + Gemma infers it -> mandatory = FAILED
    cv_text = "I am a software engineer."
    opt_profile = OptimizedCandidateProfile(
        inferred_skills=["Python"],
        core_skills=[],
    )
    from unittest.mock import patch
    with patch("app.services.candidate_domain_service.CandidateDomainService.validate_optimized_profile", return_value=opt_profile):
        context = CandidateAnalysisContext.create(cv_text=cv_text, optimized_profile=opt_profile)
    
    job = JobEvaluationContext.create({
        "id": "1",
        "title": "Software Engineer",
        "required_skills": ["Python"],
        "required_skills_are_mandatory": True
    })
    
    results = RequirementEvaluator.evaluate(
        context=context,
        job=job,
        scoring_config=ScoringConfig.load(),
        extract_term_matches_fn=ScoringEngine._extract_term_matches,
    )
    
    assert "Python" in results.missing_skills
    assert len(results.mandatory_failures) == 1
    assert "INFERRED_LLM" in results.evidence_map["req_skill_python"].cv_evidence
    assert results.evidence_map["req_skill_python"].cv_evidence.endswith("cannot satisfy mandatory requirement.")

def test_cv_contains_skill():
    # CV explicitly contains required skill -> mandatory = SATISFIED
    cv_text = "I am a software engineer with 5 years of experience in Python."
    context = CandidateAnalysisContext.create(cv_text=cv_text)
    
    job = JobEvaluationContext.create({
        "id": "1",
        "title": "Software Engineer",
        "required_skills": ["Python"],
        "required_skills_are_mandatory": True
    })
    
    results = RequirementEvaluator.evaluate(
        context=context,
        job=job,
        scoring_config=ScoringConfig.load(),
        extract_term_matches_fn=ScoringEngine._extract_term_matches,
    )
    
    assert "Python" in results.matched_skills
    assert len(results.mandatory_failures) == 0
    assert "VERIFIED_CV" in results.evidence_map["req_skill_python"].cv_evidence

def test_gemma_core_skill_grounded():
    # Gemma core skill grounded to explicit CV text -> VERIFIED/GROUNDED
    cv_text = "I have hands on experience in Python programming."
    opt_profile = OptimizedCandidateProfile(
        core_skills=["Python"],
    )
    from unittest.mock import patch
    with patch("app.services.candidate_domain_service.CandidateDomainService.validate_optimized_profile", return_value=opt_profile):
        context = CandidateAnalysisContext.create(cv_text=cv_text, optimized_profile=opt_profile)
    
    job = JobEvaluationContext.create({
        "id": "1",
        "title": "Software Engineer",
        "required_skills": ["Python"],
        "required_skills_are_mandatory": True
    })
    
    results = RequirementEvaluator.evaluate(
        context=context,
        job=job,
        scoring_config=ScoringConfig.load(),
        extract_term_matches_fn=ScoringEngine._extract_term_matches,
    )
    
    assert "Python" in results.matched_skills
    assert len(results.mandatory_failures) == 0
    assert "GROUNDED_LLM" in results.evidence_map["req_skill_python"].cv_evidence

def test_preferred_inferred_skill():
    # INFERRED_LLM can satisfy PREFERRED requirements
    cv_text = "I am a software engineer."
    opt_profile = OptimizedCandidateProfile(
        inferred_skills=["Python"],
        core_skills=[],
    )
    from unittest.mock import patch
    with patch("app.services.candidate_domain_service.CandidateDomainService.validate_optimized_profile", return_value=opt_profile):
        context = CandidateAnalysisContext.create(cv_text=cv_text, optimized_profile=opt_profile)
    
    job = JobEvaluationContext.create({
        "id": "1",
        "title": "Software Engineer",
        "required_skills": ["Python"],
        "required_skills_are_mandatory": False
    })
    
    results = RequirementEvaluator.evaluate(
        context=context,
        job=job,
        scoring_config=ScoringConfig.load(),
        extract_term_matches_fn=ScoringEngine._extract_term_matches,
    )
    
    assert "Python" not in results.matched_skills
    assert "Python" in results.inferred_skills
    assert "Python" not in results.missing_skills
    assert "INFERRED_LLM" in results.evidence_map["req_skill_python"].cv_evidence

def test_preferred_unverified_skill():
    # UNVERIFIED_LLM (core skill not in CV text) -> zero deterministic score
    cv_text = "I am a software engineer."
    opt_profile = OptimizedCandidateProfile(
        core_skills=["Python"],
    )
    from unittest.mock import patch
    with patch("app.services.candidate_domain_service.CandidateDomainService.validate_optimized_profile", return_value=opt_profile):
        context = CandidateAnalysisContext.create(cv_text=cv_text, optimized_profile=opt_profile)
    
    job = JobEvaluationContext.create({
        "id": "1",
        "title": "Software Engineer",
        "required_skills": ["Python"],
        "required_skills_are_mandatory": False
    })
    
    results = RequirementEvaluator.evaluate(
        context=context,
        job=job,
        scoring_config=ScoringConfig.load(),
        extract_term_matches_fn=ScoringEngine._extract_term_matches,
    )
    
    assert "Python" not in results.matched_skills
    assert "Python" in results.unverified_skills
    assert "Python" not in results.missing_skills
    assert "UNVERIFIED_LLM" in results.evidence_map["req_skill_python"].cv_evidence
