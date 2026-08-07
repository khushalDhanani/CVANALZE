from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock

from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.classification_types import (
    HierarchyClassificationResult,
    HierarchyMatchNode,
)
from app.schemas.job_context import JobEvaluationContext
from app.schemas.match import VacancyFitScoreBreakdown
from app.services.match_evaluators import VacancyFitEvaluator, VacancyFitResults


@pytest.fixture
def sample_candidate_context():
    ctx = MagicMock(spec=CandidateAnalysisContext)
    ctx.current_role = "Senior Flutter Developer"
    ctx.cand_tax_domain = "Information Technology"
    ctx.cand_families = ["Flutter", "Dart", "Mobile App Development", "Software Engineering"]
    ctx.candidate_experience = 5.0
    return ctx


@pytest.fixture
def sample_cand_hierarchy():
    return HierarchyClassificationResult(
        main_department=HierarchyMatchNode(id=10, name="CIS Team", confidence=0.9, reasoning="Matched CIS Team", match_status="MATCHED"),
        department=HierarchyMatchNode(id=101, name="Software Engineering", confidence=0.88, reasoning="Matched Software Engineering", match_status="MATCHED"),
        designation=HierarchyMatchNode(id=1001, name="Senior Flutter Developer", confidence=0.92, reasoning="Matched Senior Flutter Developer", match_status="MATCHED"),
        is_hierarchy_valid=True,
        validation_errors=[],
        overall_confidence=0.9,
    )


def test_1_exact_hierarchy_match(sample_candidate_context, sample_cand_hierarchy):
    """
    Test 1: Exact 3-level hierarchy match (MainDeptID=10, DeptID=101, DesigID=1001).
    hierarchy_score=100.0, high overall vacancy fit score (>=85.0), status="MATCHED".
    """
    job_ctx = MagicMock(spec=JobEvaluationContext)
    job_ctx.job_id = "JOB-101"
    job_ctx.title = "Senior Flutter Developer"
    job_ctx.department = "Software Engineering"
    job_ctx.description = "We are seeking a Senior Flutter Developer with 5+ years experience in Dart, BLoC, and mobile architecture."
    job_ctx.min_experience = 5.0
    job_ctx.raw_job = {
        "main_department_id": 10,
        "department_id": 101,
        "designation_id": 1001,
    }

    comp_results = MagicMock()
    comp_results.role_score = 95.0
    comp_results.skills_score = 90.0
    comp_results.experience_score = 100.0
    comp_results.responsibilities_score = 85.0

    def mock_embed(text, *args, **kwargs):
        return [0.9, 0.1, 0.0]

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        res = VacancyFitEvaluator.evaluate_fit(
            context=sample_candidate_context,
            job=job_ctx,
            cv_text=job_ctx.description,
            cand_hierarchy=sample_cand_hierarchy,
            comp_results=comp_results,
            threshold=60.0,
        )

        assert isinstance(res, VacancyFitResults)
        assert res.match_status == "MATCHED"
        assert res.score_breakdown.hierarchy_score == 100.0
        assert res.vacancy_fit_score >= 85.0
        assert res.score_breakdown.hierarchy_mismatch_penalty == 0.0


def test_2_partial_hierarchy_match(sample_candidate_context, sample_cand_hierarchy):
    """
    Test 2: Partial hierarchy match (MainDeptID=10, DeptID=101 match, but DesigID differs: 1002 vs 1001).
    hierarchy_score=80.0, overall fit score >= 60.0, status="MATCHED".
    """
    job_ctx = MagicMock(spec=JobEvaluationContext)
    job_ctx.job_id = "JOB-102"
    job_ctx.title = "Backend Python Engineer"
    job_ctx.department = "Software Engineering"
    job_ctx.description = "Software Engineering department looking for Python developer."
    job_ctx.min_experience = 4.0
    job_ctx.raw_job = {
        "main_department_id": 10,
        "department_id": 101,
        "designation_id": 1002,  # Differs from candidate 1001
    }

    comp_results = MagicMock()
    comp_results.role_score = 80.0
    comp_results.skills_score = 75.0
    comp_results.experience_score = 100.0
    comp_results.responsibilities_score = 70.0

    def mock_embed(text, *args, **kwargs):
        return [0.8, 0.2, 0.0]

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        res = VacancyFitEvaluator.evaluate_fit(
            context=sample_candidate_context,
            job=job_ctx,
            cv_text=job_ctx.description,
            cand_hierarchy=sample_cand_hierarchy,
            comp_results=comp_results,
            threshold=60.0,
        )

        assert res.match_status == "MATCHED"
        assert res.score_breakdown.hierarchy_score == 80.0
        assert res.vacancy_fit_score >= 60.0


def test_3_hierarchy_mismatch(sample_candidate_context, sample_cand_hierarchy):
    """
    Test 3: Hierarchy mismatch (Candidate MainDeptID=10 'CIS Team' vs Vacancy MainDeptID=20 'Manufacturing').
    hierarchy_score=0.0, penalty applied, score capped <= 45.0, status="NO_STRONG_VACANCY_MATCH".
    """
    job_ctx = MagicMock(spec=JobEvaluationContext)
    job_ctx.job_id = "JOB-201"
    job_ctx.title = "Plant Operations Executive"
    job_ctx.department = "Manufacturing"
    job_ctx.description = "Manufacturing plant executive position."
    job_ctx.min_experience = 3.0
    job_ctx.raw_job = {
        "main_department_id": 20,  # Manufacturing (candidate is 10 CIS)
        "department_id": 201,
        "designation_id": 2001,
    }

    comp_results = MagicMock()
    comp_results.role_score = 50.0
    comp_results.skills_score = 50.0
    comp_results.experience_score = 100.0

    res = VacancyFitEvaluator.evaluate_fit(
        context=sample_candidate_context,
        job=job_ctx,
        cv_text=job_ctx.description,
        cand_hierarchy=sample_cand_hierarchy,
        comp_results=comp_results,
        threshold=60.0,
    )

    assert res.match_status == "NO_STRONG_VACANCY_MATCH"
    assert res.score_breakdown.hierarchy_score == 0.0
    assert res.score_breakdown.hierarchy_mismatch_penalty > 0.0
    assert res.vacancy_fit_score <= 45.0


def test_4_strong_skills_but_wrong_department(sample_candidate_context, sample_cand_hierarchy):
    """
    Test 4: Strong skills match (100%) but candidate is in wrong department (Human Resources 25 vs Vacancy Manufacturing 20).
    High embedding similarity & 100% skills CANNOT override invalid/mismatched department hierarchy!
    Fit score capped at <= 45.0, status="NO_STRONG_VACANCY_MATCH".
    """
    job_ctx = MagicMock(spec=JobEvaluationContext)
    job_ctx.job_id = "JOB-202"
    job_ctx.title = "Manufacturing Specialist"
    job_ctx.department = "Manufacturing"
    job_ctx.description = "Manufacturing specialist with python and data skills."
    job_ctx.min_experience = 3.0
    job_ctx.raw_job = {
        "main_department_id": 20,  # Manufacturing (candidate hierarchy has 10 CIS)
        "department_id": 201,
    }

    comp_results = MagicMock()
    comp_results.role_score = 100.0
    comp_results.skills_score = 100.0
    comp_results.experience_score = 100.0
    comp_results.responsibilities_score = 100.0

    def mock_embed(text, *args, **kwargs):
        return [0.99, 0.0, 0.0]  # High embedding similarity

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        res = VacancyFitEvaluator.evaluate_fit(
            context=sample_candidate_context,
            job=job_ctx,
            cv_text=job_ctx.description,
            cand_hierarchy=sample_cand_hierarchy,
            comp_results=comp_results,
            threshold=60.0,
        )

        assert res.match_status == "NO_STRONG_VACANCY_MATCH"
        assert res.vacancy_fit_score <= 45.0
        assert "Main Department or hierarchy mismatch" in res.reason


def test_5_experience_mismatch(sample_candidate_context, sample_cand_hierarchy):
    """
    Test 5: Hierarchy and skills match, but candidate experience (1 year) is far below required (10 years).
    Experience score penalty drops overall fit score below threshold (60.0), returning NO_STRONG_VACANCY_MATCH.
    """
    sample_candidate_context.candidate_experience = 1.0  # Only 1 year experience

    job_ctx = MagicMock(spec=JobEvaluationContext)
    job_ctx.job_id = "JOB-103"
    job_ctx.title = "VP of Software Engineering"
    job_ctx.department = "Software Engineering"
    job_ctx.description = "Executive engineering leadership role requiring 10+ years experience."
    job_ctx.min_experience = 10.0
    job_ctx.raw_job = {
        "main_department_id": 10,
        "department_id": 101,
        "designation_id": 1001,
    }

    comp_results = MagicMock()
    comp_results.role_score = 60.0
    comp_results.skills_score = 70.0
    comp_results.experience_score = 10.0  # Low experience match

    res = VacancyFitEvaluator.evaluate_fit(
        context=sample_candidate_context,
        job=job_ctx,
        cv_text=job_ctx.description,
        cand_hierarchy=sample_cand_hierarchy,
        comp_results=comp_results,
        threshold=60.0,
    )

    assert res.match_status == "NO_STRONG_VACANCY_MATCH"
    assert res.score_breakdown.experience_score <= 20.0
    assert res.vacancy_fit_score < 60.0


def test_6_semantic_only_false_positive(sample_candidate_context, sample_cand_hierarchy):
    """
    Test 6: High semantic embedding similarity (buzzwords overlap) but low skills and wrong hierarchy.
    Penalty & low component scores result in NO_STRONG_VACANCY_MATCH.
    """
    job_ctx = MagicMock(spec=JobEvaluationContext)
    job_ctx.job_id = "JOB-301"
    job_ctx.title = "Quality Control Lead Chemist"
    job_ctx.department = "Quality Control"
    job_ctx.description = "Lead chemist position requiring HPLC, wet chemistry, and validation."
    job_ctx.min_experience = 6.0
    job_ctx.raw_job = {
        "main_department_id": 30,  # QC (candidate is CIS 10)
        "department_id": 301,
    }

    comp_results = MagicMock()
    comp_results.role_score = 20.0
    comp_results.skills_score = 15.0
    comp_results.experience_score = 50.0

    def mock_embed(text, *args, **kwargs):
        return [0.95, 0.05, 0.0]  # False positive high embedding similarity

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        res = VacancyFitEvaluator.evaluate_fit(
            context=sample_candidate_context,
            job=job_ctx,
            cv_text=job_ctx.description,
            cand_hierarchy=sample_cand_hierarchy,
            comp_results=comp_results,
            threshold=60.0,
        )

        assert res.match_status == "NO_STRONG_VACANCY_MATCH"
        assert res.vacancy_fit_score <= 45.0


def test_7_strong_overall_match(sample_candidate_context, sample_cand_hierarchy):
    """
    Test 7: Strong overall match across all dimensions (Exact hierarchy, high skills, target experience, high semantic fit).
    Returns MATCHED with score breakdown.
    """
    job_ctx = MagicMock(spec=JobEvaluationContext)
    job_ctx.job_id = "JOB-101"
    job_ctx.title = "Senior Flutter Developer"
    job_ctx.department = "Software Engineering"
    job_ctx.description = "Senior Mobile Developer position."
    job_ctx.min_experience = 4.0
    job_ctx.raw_job = {
        "main_department_id": 10,
        "department_id": 101,
        "designation_id": 1001,
    }

    comp_results = MagicMock()
    comp_results.role_score = 95.0
    comp_results.skills_score = 95.0
    comp_results.experience_score = 100.0

    def mock_embed(text, *args, **kwargs):
        return [0.9, 0.1, 0.0]

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        res = VacancyFitEvaluator.evaluate_fit(
            context=sample_candidate_context,
            job=job_ctx,
            cv_text=job_ctx.description,
            cand_hierarchy=sample_cand_hierarchy,
            comp_results=comp_results,
            threshold=60.0,
        )

        assert res.match_status == "MATCHED"
        assert res.vacancy_fit_score >= 85.0
        assert isinstance(res.score_breakdown, VacancyFitScoreBreakdown)
        assert res.score_breakdown.hierarchy_score == 100.0
        assert res.score_breakdown.skills_score == 95.0
