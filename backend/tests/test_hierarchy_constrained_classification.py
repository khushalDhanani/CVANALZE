from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock

from app.schemas.classification_types import (
    HierarchyClassificationResult,
    HierarchyMatchNode,
    MainDepartmentClassificationResult,
)
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService


@pytest.fixture
def sample_hierarchy_data():
    main_depts = [
        {"id": 10, "name": "CIS Team"},
        {"id": 20, "name": "Manufacturing"},
        {"id": 30, "name": "Quality Control"},
    ]
    depts = [
        {"id": 101, "name": "Software Engineering", "main_department_id": 10},
        {"id": 102, "name": "IT Infrastructure", "main_department_id": 10},
        {"id": 201, "name": "Plant Operations", "main_department_id": 20},
    ]
    desigs = [
        {"id": 1001, "name": "Senior Flutter Developer", "department_id": 101, "main_department_id": 10},
        {"id": 1002, "name": "Backend Python Engineer", "department_id": 101, "main_department_id": 10},
        {"id": 1003, "name": "DevOps Lead", "department_id": 102, "main_department_id": 10},
    ]
    return main_depts, depts, desigs


def test_1_strong_hierarchy_match(sample_hierarchy_data):
    """
    Test 1: Strong hierarchy match resolves MainDeptID=10 ('CIS Team'),
    DeptID=101 ('Software Engineering'), and DesigID=1001 ('Senior Flutter Developer').
    """
    main_depts, depts, desigs = sample_hierarchy_data

    def mock_embed(text, *args, **kwargs):
        if "Main Department ID: 10" in text or "CIS Team" in text or "Mobile Engineer" in text:
            return [1.0, 0.0, 0.0]
        elif "Department ID: 101" in text or "Software Engineering" in text:
            return [0.95, 0.05, 0.0]
        elif "Designation ID: 1001" in text or "Senior Flutter Developer" in text:
            return [0.98, 0.02, 0.0]
        return [0.1, 0.1, 0.8]

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        result = DynamicTaxonomyService.classify_organization_hierarchy(
            role_or_summary="Senior Flutter & Mobile Engineer",
            skills=["Flutter", "Dart", "BLoC"],
            domain="Information Technology",
            main_departments=main_depts,
            departments=depts,
            designations=desigs,
            threshold=0.50,
        )

        assert isinstance(result, HierarchyClassificationResult)
        assert result.main_department.match_status == "MATCHED"
        assert result.main_department.id == 10
        assert result.main_department.name == "CIS Team"

        assert result.department.match_status == "MATCHED"
        assert result.department.id == 101
        assert result.department.name == "Software Engineering"

        assert result.designation.match_status == "MATCHED"
        assert result.designation.id == 1001
        assert result.designation.name == "Senior Flutter Developer"
        assert result.is_hierarchy_valid is True


def test_2_semantic_name_mismatch(sample_hierarchy_data):
    """
    Test 2: Industry role 'Mobile App Programmer' differs from internal labels ('CIS Team' -> 'Software Engineering').
    Semantic vector embedding maps candidate through the exact hierarchy.
    """
    main_depts, depts, desigs = sample_hierarchy_data

    def mock_embed(text, *args, **kwargs):
        if "Main Department ID: 10" in text or "CIS Team" in text or "Mobile App Programmer" in text:
            return [1.0, 0.0, 0.0]
        elif "Department ID: 101" in text or "Software Engineering" in text:
            return [0.90, 0.10, 0.0]
        elif "Designation ID: 1001" in text or "Senior Flutter Developer" in text:
            return [0.92, 0.08, 0.0]
        return [0.0, 0.0, 1.0]

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        result = DynamicTaxonomyService.classify_organization_hierarchy(
            role_or_summary="Mobile App Programmer",
            skills=["Mobile Apps", "iOS", "Android"],
            domain="IT",
            main_departments=main_depts,
            departments=depts,
            designations=desigs,
            threshold=0.50,
        )

        assert result.main_department.id == 10
        assert result.department.id == 101
        assert result.designation.id == 1001


def test_3_ambiguous_department(sample_hierarchy_data):
    """
    Test 3: 2 departments under resolved MainDeptID=10 return identical similarity vectors (gap < 0.05).
    Department level returns NO_STRONG_DEPARTMENT_MATCH and designation search is skipped.
    """
    main_depts, depts, desigs = sample_hierarchy_data

    def mock_embed(text, *args, **kwargs):
        if "Main Department ID: 10" in text or "Generalist" in text:
            return [1.0, 0.0, 0.0]
        elif "Department ID: 101" in text or "Department ID: 102" in text:
            return [0.5, 0.5, 0.0]  # Identical score for both departments
        return [0.1, 0.1, 0.8]

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        result = DynamicTaxonomyService.classify_organization_hierarchy(
            role_or_summary="Generalist IT Worker",
            skills=["General"],
            domain="IT",
            main_departments=main_depts,
            departments=depts,
            designations=desigs,
            threshold=0.40,
            ambiguity_gap=0.05,
        )

        assert result.main_department.match_status == "MATCHED"
        assert result.main_department.id == 10
        assert result.department.match_status == "NO_STRONG_DEPARTMENT_MATCH"
        assert result.department.id is None
        assert result.designation.match_status == "NO_STRONG_DESIGNATION_MATCH"
        assert result.designation.id is None


def test_4_ambiguous_designation(sample_hierarchy_data):
    """
    Test 4: MainDept and Dept resolve, but 2 designations under DeptID=101 have identical similarity.
    Designation level returns NO_STRONG_DESIGNATION_MATCH.
    """
    main_depts, depts, desigs = sample_hierarchy_data

    def mock_embed(text, *args, **kwargs):
        if "Main Department ID: 10" in text or "Full Stack" in text:
            return [1.0, 0.0, 0.0]
        elif "Department ID: 101" in text or "Software Engineering" in text:
            return [0.9, 0.1, 0.0]
        elif "Designation ID: 1001" in text or "Designation ID: 1002" in text:
            return [0.6, 0.6, 0.0]  # Equal top similarity between 1001 & 1002
        return [0.0, 0.0, 1.0]

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):
        result = DynamicTaxonomyService.classify_organization_hierarchy(
            role_or_summary="Full Stack Generalist",
            skills=["Software"],
            domain="IT",
            main_departments=main_depts,
            departments=depts,
            designations=desigs,
            threshold=0.40,
            ambiguity_gap=0.05,
        )

        assert result.main_department.id == 10
        assert result.department.id == 101
        assert result.designation.match_status == "NO_STRONG_DESIGNATION_MATCH"
        assert result.designation.id is None


def test_5_invalid_hierarchy(sample_hierarchy_data):
    """
    Test 5: Parent-child hierarchy validation fails (e.g. designation does not belong to main dept in MSSQL DB).
    Child designation resolution is invalidated cleanly.
    """
    main_depts, depts, desigs = sample_hierarchy_data
    mock_db = MagicMock()

    def mock_embed(text, *args, **kwargs):
        if "Main Department ID: 10" in text or "CIS Team" in text or "Senior Flutter Developer" in text:
            return [1.0, 0.0, 0.0]
        elif "Department ID: 101" in text or "Software Engineering" in text:
            return [0.95, 0.05, 0.0]
        elif "Designation ID: 1001" in text or "Senior Flutter Developer" in text:
            return [0.98, 0.02, 0.0]
        return [0.1, 0.1, 0.8]

    with patch("app.repositories.mssql.organization_source.OrganizationSourceRepository.validate_hierarchy") as mock_val, \
         patch("app.services.embedding_service.EmbeddingService.generate_embedding", side_effect=mock_embed):

        mock_val.return_value = {
            "is_valid": False,
            "errors": ["Designation ID 1001 belongs to Main Dept 20, not 10."],
            "details": {},
        }

        result = DynamicTaxonomyService.classify_organization_hierarchy(
            role_or_summary="Senior Flutter Developer",
            skills=["Software Engineering"],
            domain="IT",
            main_departments=main_depts,
            departments=depts,
            designations=desigs,
            db_session=mock_db,
        )

        assert result.is_hierarchy_valid is False
        assert len(result.validation_errors) > 0
        assert result.designation.match_status == "NO_STRONG_DESIGNATION_MATCH"
        assert result.designation.id is None


def test_6_no_match(sample_hierarchy_data):
    """
    Test 6: Candidate profile similarity is low across all departments (< threshold).
    Engine returns NO_STRONG_MAIN_DEPARTMENT_MATCH and skips child levels.
    """
    main_depts, depts, desigs = sample_hierarchy_data

    result = DynamicTaxonomyService.classify_organization_hierarchy(
        role_or_summary="Unrelated Skill",
        skills=["Astronomer"],
        domain="Astrophysics",
        main_departments=main_depts,
        departments=depts,
        designations=desigs,
        threshold=0.85,
    )

    assert result.main_department.match_status == "NO_STRONG_MAIN_DEPARTMENT_MATCH"
    assert result.main_department.id is None
    assert result.department.match_status == "NO_STRONG_DEPARTMENT_MATCH"
    assert result.designation.match_status == "NO_STRONG_DESIGNATION_MATCH"


def test_7_embedding_fallback(sample_hierarchy_data):
    """
    Test 7: When vector embedding service returns None (e.g., Ollama offline),
    engine falls back gracefully to rule-based keyword semantic matching and resolves hierarchy.
    """
    main_depts, depts, desigs = sample_hierarchy_data

    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=None):
        result = DynamicTaxonomyService.classify_organization_hierarchy(
            role_or_summary="Senior Flutter Developer",
            skills=["Flutter", "Software Engineering"],
            domain="Information Technology",
            main_departments=main_depts,
            departments=depts,
            designations=desigs,
            threshold=0.50,
        )

        assert result.main_department.match_status == "MATCHED"
        assert result.main_department.id == 10
        assert result.department.match_status == "MATCHED"
        assert result.department.id == 101
        assert result.designation.match_status == "MATCHED"
        assert result.designation.id == 1001
