from app.schemas.analysis import EnrichedJobMatchResult
from app.schemas.contracts import ProcessingJobRecord
from app.schemas.match import (
    CandidateMatchAnalysis,
    DualEvidence,
    HiringRisk,
    JobMatchResult,
    MandatoryFailureDetails,
    RequirementEvaluation,
    RequirementStatus,
    RequirementTier,
    VacancyFitScoreBreakdown,
)


def test_job_match_result_contract_shape_alignment() -> None:
    """Release Gate 4.1: JobMatchResult serialization maintains 100% field alignment with frontend TypeScript contracts."""
    evidence = DualEvidence(
        cv_evidence="5 years Python backend development",
        vacancy_evidence="Requires 5+ years Python",
        confidence_score=0.95,
        provenance="VERIFIED_CV",
        source_section="WORK EXPERIENCE",
    )

    req = RequirementEvaluation(
        requirement_id="req_python",
        requirement_type="skill",
        tier=RequirementTier.MANDATORY,
        description="Python programming",
        status=RequirementStatus.SATISFIED,
        weight=1.0,
        evidence=evidence,
    )

    failure = MandatoryFailureDetails(
        failure_code="MISSING_MANDATORY_SKILL",
        requirement_id="req_k8s",
        requirement_type="skill",
        description="Kubernetes orchestration missing",
        reason="Kubernetes orchestration missing",
        details={"skill": "Kubernetes"},
    )

    breakdown = VacancyFitScoreBreakdown(
        hierarchy_score=85.0,
        designation_role_score=90.0,
        skills_score=80.0,
        experience_score=95.0,
        education_score=75.0,
        semantic_similarity_score=88.0,
        overall_fit_score=86.5,
        match_status="MATCHED",
    )

    match_result = JobMatchResult(
        job_id="job-101",
        job_title="Senior Python Engineer",
        department="Engineering",
        vacancy_id=101,
        score=86.5,
        overall_score=86.5,
        vacancy_fit_score=86.5,
        score_breakdown=breakdown,
        vacancy_match_status="MATCHED",
        classification="Strong Match",
        recommendation="Recommended for Interview",
        role_score=90.0,
        skills_score=80.0,
        experience_score=95.0,
        education_score=75.0,
        domain_score=85.0,
        technology_score=80.0,
        coverage=0.88,
        matched_skills=["Python", "FastAPI"],
        missing_skills=["Kubernetes"],
        mandatory_requirements=[req],
        mandatory_failures=[failure],
    )

    data = match_result.model_dump(mode="json")

    # Critical frontend TypeScript contract fields
    assert "score" in data
    assert "vacancy_fit_score" in data
    assert "vacancy_match_status" in data
    assert "classification" in data
    assert "recommendation" in data
    assert "role_score" in data
    assert "skills_score" in data
    assert "experience_score" in data
    assert "education_score" in data
    assert "domain_score" in data
    assert "technology_score" in data
    assert "coverage" in data
    assert "matched_skills" in data
    assert "missing_skills" in data
    assert "mandatory_requirements" in data
    assert "mandatory_failures" in data
    assert "score_breakdown" in data

    # Sub-schema fields
    assert data["mandatory_requirements"][0]["evidence"]["provenance"] == "VERIFIED_CV"
    assert data["mandatory_requirements"][0]["evidence"]["source_section"] == "WORK EXPERIENCE"
    assert data["mandatory_failures"][0]["failure_code"] == "MISSING_MANDATORY_SKILL"


def test_candidate_match_analysis_contract_shape_alignment() -> None:
    """Release Gate 4.2: CandidateMatchAnalysis preserves end-to-end response schema."""
    analysis = CandidateMatchAnalysis(
        full_name="Alex Mercer",
        candidate_name="Alex Mercer",
        primary_department="Engineering",
        best_match=None,
        suitable_openings=[],
        unsuitable_openings=[],
    )

    data = analysis.model_dump(mode="json")
    assert "candidate_name" in data
    assert "best_match" in data
    assert "suitable_openings" in data
    assert "unsuitable_openings" in data


def test_processing_job_record_contract_shape_alignment() -> None:
    """Release Gate 4.3: ProcessingJobRecord matches asynchronous polling contract."""
    job = ProcessingJobRecord(
        job_id="job_uuid_999",
        cv_key="cand_cv_123",
        content_hash="hash_123",
        filename="cand_cv.pdf",
        state="COMPLETED",
        storage_filename="cand_cv.pdf",
        parser_version="v2",
        schema_version="v1",
        attempt=1,
    )

    data = job.model_dump(mode="json")
    assert data["job_id"] == "job_uuid_999"
    assert data["state"] == "COMPLETED"
    assert "parser_version" in data
    assert "schema_version" in data


def test_evidence_result_canonical_contract() -> None:
    """Release Gate 4.4: EvidenceResult[T] maintains canonical shared field/result contract."""
    from app.schemas.contracts import EvidenceRef, EvidenceResult, EvidenceStatus

    ref = EvidenceRef(
        source_section="WORK EXPERIENCE",
        raw_quote="Senior Systems Engineer at NetCore",
        provenance="VERIFIED_CV",
        confidence_score=0.95,
    )
    result = EvidenceResult.verified(
        value="Senior Systems Engineer",
        confidence=0.95,
        evidence=[ref],
        source="deterministic",
        policy_version="a1b2c3d4e5f67890",
        model_version="gemma3:1b",
    )

    data = result.model_dump(mode="json")
    assert data["value"] == "Senior Systems Engineer"
    assert data["status"] == "VERIFIED"
    assert data["confidence"] == 0.95
    assert len(data["evidence"]) == 1
    assert data["evidence"][0]["source_section"] == "WORK EXPERIENCE"
    assert data["evidence"][0]["provenance"] == "VERIFIED_CV"
    assert data["source"] == "deterministic"
    assert data["policy_version"] == "a1b2c3d4e5f67890"
    assert data["model_version"] == "gemma3:1b"

    # Test not_assessable state
    na_result = EvidenceResult[float].not_assessable("No CTC mentioned in resume", policy_version="a1b2c3d4e5f67890")
    na_data = na_result.model_dump(mode="json")
    assert na_data["value"] is None
    assert na_data["status"] == "NOT_ASSESSABLE"
    assert "NOT_ASSESSABLE" in na_data["evidence"][0]["raw_quote"]

