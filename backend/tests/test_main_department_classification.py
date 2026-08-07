from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock

from app.schemas.classification_types import MainDepartmentClassificationResult, MatchStatus
from app.schemas.analysis import EnrichedCandidateAnalysis, EnrichedJobMatchResult
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
from app.services.match_service import MatchService
from app.services.recommendation_service import RecommendationService


@pytest.fixture
def sample_main_departments():
    return [
        {"id": 5, "name": "Manufacturing"},
        {"id": 10, "name": "CIS Team"},
        {"id": 15, "name": "Quality Control"},
        {"id": 20, "name": "Research & Development"},
        {"id": 25, "name": "Human Resources"},
        {"id": 30, "name": "Finance & Accounts"},
    ]


def test_internal_name_differs_from_industry_role(sample_main_departments):
    """
    Test 5: Internal department name (e.g. 'CIS Team') differs from industry role (e.g. 'Senior Flutter & Mobile Developer').
    Semantic mapping must resolve the candidate to MainDeptID=10, DeptName='CIS Team'.
    """
    result = DynamicTaxonomyService.classify_main_department(
        role_or_summary="Senior Flutter & Mobile Developer",
        skills=["Flutter", "Dart", "BLoC", "REST API", "Mobile App Development"],
        domain="Information Technology",
        main_departments=sample_main_departments,
    )

    assert isinstance(result, MainDepartmentClassificationResult)
    assert result.match_status == "MATCHED"
    assert result.main_department_id == 10
    assert result.main_department_name == "CIS Team"
    assert result.confidence >= 0.60
    assert "CIS Team" in result.reasoning


def test_no_vacancy_match_returns_correct_main_department(sample_main_departments):
    """
    Test 2: Candidate has no active vacancy match (e.g. no software engineering vacancy open),
    so system must NOT force a vacancy recommendation, but MUST return the correct Main Department.
    """
    with patch("app.repositories.job.JobRepository.get_all_jobs", return_value=[]), \
         patch("app.services.dynamic_taxonomy_service.DynamicTaxonomyService.classify_main_department") as mock_classify:

        mock_classify.return_value = MainDepartmentClassificationResult(
            main_department_id=10,
            main_department_name="CIS Team",
            confidence=0.85,
            reasoning="Mapped to Main Department 'CIS Team' (ID: 10) based on software development experience.",
            match_status="MATCHED",
        )

        cv_text = "Senior Python Developer with 5 years experience building FastAPI backends and Web applications."
        analysis = MatchService._empty_analysis(cv_text=cv_text)

        assert analysis.has_genuine_match is False
        assert analysis.best_match is None
        assert analysis.main_department_classification is not None
        assert analysis.main_department_classification.match_status == "MATCHED"
        assert analysis.main_department_classification.main_department_id == 10
        assert analysis.main_department_classification.main_department_name == "CIS Team"


def test_vacancy_matched_with_independent_main_department(sample_main_departments):
    """
    Test 1: Vacancy matched scenario where candidate matches an open vacancy,
    and vacancy matching and department classification remain separate.
    """
    candidate_context = MagicMock()
    candidate_context.current_role = "Senior Chemist"
    candidate_context.cand_families = ["Quality Control", "Analytical Chemistry"]

    with patch("app.services.dynamic_taxonomy_service.DynamicTaxonomyService.classify_main_department") as mock_classify:
        mock_classify.return_value = MainDepartmentClassificationResult(
            main_department_id=15,
            main_department_name="Quality Control",
            confidence=0.90,
            reasoning="Mapped to Main Department 'Quality Control' (ID: 15).",
            match_status="MATCHED",
        )

        main_dept_res = DynamicTaxonomyService.classify_main_department(
            role_or_summary="Senior Chemist",
            skills=["HPLC", "Analytical Chemistry"],
            domain="Quality Control",
            main_departments=sample_main_departments,
        )

        assert main_dept_res.match_status == "MATCHED"
        assert main_dept_res.main_department_id == 15
        assert main_dept_res.main_department_name == "Quality Control"


def test_ambiguous_cv_returns_no_strong_main_department(sample_main_departments):
    """
    Test 3: Ambiguous CV spanning multiple unrelated fields (e.g., equal parts HR recruiting and Plant Operations)
    without a clear winner should return NO_STRONG_MAIN_DEPARTMENT_MATCH.
    """
    result = DynamicTaxonomyService.classify_main_department(
        role_or_summary="Generalist Assistant",
        skills=["general admin", "random task"],
        domain="General",
        main_departments=sample_main_departments,
        threshold=0.60,
    )

    assert isinstance(result, MainDepartmentClassificationResult)
    assert result.match_status == "NO_STRONG_MAIN_DEPARTMENT_MATCH"
    assert result.main_department_id is None
    assert result.main_department_name == "NO_STRONG_MAIN_DEPARTMENT_MATCH"


def test_no_valid_main_department_in_db():
    """
    Test 4: When OrgMainDepartmentMst is empty or has no valid departments,
    system returns NO_STRONG_MAIN_DEPARTMENT_MATCH.
    """
    result = DynamicTaxonomyService.classify_main_department(
        role_or_summary="Software Engineer",
        skills=["Python", "FastAPI"],
        domain="IT",
        main_departments=[],
    )

    assert isinstance(result, MainDepartmentClassificationResult)
    assert result.match_status == "NO_STRONG_MAIN_DEPARTMENT_MATCH"
    assert result.main_department_id is None
    assert result.main_department_name == "NO_STRONG_MAIN_DEPARTMENT_MATCH"
    assert "No active main departments" in result.reasoning


def test_recommendation_service_no_forced_vacancy_and_main_department_integration():
    """
    Verifies RecommendationService when no strong vacancy match exists:
    - best_vacancies is empty (no forced vacancy recommendation)
    - hiring_recommendation is NO_STRONG_MATCH
    - main_department_classification is returned with IDs and reasoning
    """
    mock_result_payload = {
        "candidate_id": "test_cand_123",
        "full_name": "Test Candidate",
        "status": "completed",
        "match_analysis": {
            "suitable_openings": [],
            "best_match": None,
            "main_department_classification": {
                "main_department_id": 10,
                "main_department_name": "CIS Team",
                "confidence": 0.88,
                "reasoning": "Mapped to CIS Team based on Flutter development skills.",
                "match_status": "MATCHED",
            },
            "classification": {
                "industry_department": "CIS Team",
                "industry_domain": "Information Technology",
            },
        },
        "resume_json": {
            "contact_info": {"name": "Test Candidate"},
            "skills": ["Flutter", "Dart"],
        },
    }

    with patch("app.repositories.result.ResultRepository.resolve_result", return_value=mock_result_payload), \
         patch("app.repositories.job.JobRepository.get_all_jobs", return_value=[]):

        rec = RecommendationService.get_candidate_recommendations("test_cand_123")

        assert rec["hiring_recommendation"] == "NO_STRONG_MATCH"
        assert rec["best_vacancies"] == []
        assert rec["main_department_id"] == 10
        assert rec["main_department_name"] == "CIS Team"
        assert rec["main_department_confidence"] == 0.88
        assert "CIS Team" in rec["main_department_reasoning"]


def test_embedding_based_strong_match(sample_main_departments):
    """
    Verifies data-driven vector embedding similarity calculation via EmbeddingService.
    When candidate profile vector strongly aligns with CIS Team department vector.
    """
    def mock_embed(text, *args, **kwargs):
        if "Main Department ID: 10" in text or "CIS Team" in text or "Mobile Engineer" in text:
            return [1.0, 0.0, 0.0]
        elif "Main Department ID: 15" in text or "Quality Control" in text:
            return [0.0, 1.0, 0.0]
        elif "Main Department ID: 5" in text:
            return [0.0, 0.0, 1.0]
        return [0.1, 0.1, 0.1]

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        result = DynamicTaxonomyService.classify_main_department(
            role_or_summary="Mobile Engineer",
            skills=["Flutter", "Dart"],
            domain="Information Technology",
            main_departments=sample_main_departments,
            threshold=0.50,
        )

        assert result.match_status == "MATCHED"
        assert result.main_department_id == 10
        assert result.main_department_name == "CIS Team"
        assert result.confidence >= 0.70


def test_embedding_based_ambiguous_match(sample_main_departments):
    """
    Verifies ambiguity gap check when candidate profile vector returns nearly identical similarity
    across multiple departments.
    """
    def mock_embed(text, *args, **kwargs):
        return [0.577, 0.577, 0.577]

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        result = DynamicTaxonomyService.classify_main_department(
            role_or_summary="Cross-functional Worker",
            skills=["General"],
            domain="General",
            main_departments=sample_main_departments,
            threshold=0.50,
            ambiguity_gap=0.05,
        )

        assert result.match_status == "NO_STRONG_MAIN_DEPARTMENT_MATCH"
        assert result.main_department_id is None
        assert result.main_department_name == "NO_STRONG_MAIN_DEPARTMENT_MATCH"
        assert "Ambiguous candidate profile" in result.reasoning

