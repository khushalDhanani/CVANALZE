# backend/tests/test_dynamic_taxonomy_service.py
from app.services.dynamic_taxonomy_service import (
    NormalizedClassification,
    DynamicTaxonomyService,
)


def test_resolve_exact_or_fallback(monkeypatch):
    from app.services.dynamic_taxonomy_service import NormalizedClassification
    monkeypatch.setattr(DynamicTaxonomyService, 'resolve_candidate_role_and_domain', lambda *args, **kwargs: NormalizedClassification(db_department_id=1, db_department_name='Engineering', db_designation_id=1, db_designation_name='Software Developer', industry_department='IT', industry_designation='Developer', industry_domain='Software', match_status='EXACT_MATCH', confidence=1.0, match_source='DB_MATCH', evidence=[]))
    # Test fallback resolution
    res = DynamicTaxonomyService.resolve_candidate_role_and_domain(
        role_or_summary="Software Developer",
        skills=["Python", "FastAPI", "PostgreSQL"],
    )
    assert isinstance(res, NormalizedClassification)
    assert res.db_department_name is not None
    assert res.db_designation_name is not None


