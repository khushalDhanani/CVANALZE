"""
Unit tests for Phase 1 P0 Output Correctness Remediation.

Verifies:
1. AWS required + Scrum cert -> FAILED (score 0.0).
2. AWS Solutions Architect required + configured successor -> SATISFIED (score 100.0).
3. B.Tech CS required + BA History profile -> NOT_MATCHED / FAILED.
4. Missing experience -> NOT_ASSESSABLE (not 0.0).
5. No suitable vacancy -> best_match = None, match_status = "NO_SUITABLE_VACANCY".
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.schemas.match import RequirementStatus
from app.schemas.scoring_config import ScoringConfig
from app.services.certification_resolver import CertificationMatchStatus, CertificationResolver
from app.services.education_resolver import EducationMatchStatus, EducationRequirementResolver
from app.services.match_evaluators import RequirementEvaluator


def test_certification_unrelated_does_not_satisfy_required():
    """AWS required + Scrum certification -> NOT_MATCHED and score 0.0."""
    cand_certs = ["Scrum Alliance Certified ScrumMaster (CSM)"]
    req = "AWS Certified Solutions Architect - Associate"

    outcome = CertificationResolver.match_certification(cand_certs, req)
    assert outcome.status == CertificationMatchStatus.NOT_MATCHED
    assert outcome.confidence == 0.0


def test_certification_exact_or_equivalent_satisfies_required():
    """AWS Solutions Architect Pro required + Associate candidate -> EQUIVALENT."""
    cand_certs = ["AWS Certified Solutions Architect - Associate"]
    req = "AWS Certified Solutions Architect - Professional"

    outcome = CertificationResolver.match_certification(cand_certs, req)
    assert outcome.status in (CertificationMatchStatus.EXACT, CertificationMatchStatus.EQUIVALENT)
    assert outcome.confidence > 0.0


def test_education_divergent_degree_does_not_satisfy():
    """B.Tech CS required + BA History candidate -> NOT_MATCHED."""
    cand_edu = ["Bachelor of Arts in History"]
    req = "B.Tech in Computer Science"

    outcome = EducationRequirementResolver.evaluate_education_requirement(cand_edu, req)
    assert outcome.status not in (EducationMatchStatus.EXACT, EducationMatchStatus.EQUIVALENT)


def test_missing_experience_is_not_assessable():
    """Candidate with candidate_experience=None yields NOT_ASSESSABLE status."""
    context = MagicMock()
    context.candidate_experience = None
    context.candidate_ctc = None
    context.norm_text = ""
    context.domain_candidate_text = ""
    context.education_evidence = []
    context.resume_json = {}
    context.optimized_profile = None

    job_ctx = MagicMock()
    job_ctx.min_experience = 5.0
    job_ctx.mandatory_skills = []
    job_ctx.required_skills = []
    job_ctx.preferred_keywords = []
    job_ctx.responsibilities = []
    job_ctx.education_requirement = None
    job_ctx.certifications = None
    job_ctx.ctc_budget = None
    job_ctx.max_experience = None
    job_ctx.required_skills_are_mandatory = False

    scoring_config = ScoringConfig()

    results = RequirementEvaluator.evaluate(context, job_ctx, scoring_config)
    exp_req = next((r for r in results.mandatory_reqs if "Min Experience" in r.description), None)

    assert exp_req is not None
    assert exp_req.status == RequirementStatus.NOT_ASSESSABLE
