# backend/tests/test_dynamic_taxonomy_service.py
from app.services.dynamic_taxonomy_service import (
    DynamicTaxonomyResult,
    DynamicTaxonomyService,
)


def test_resolve_exact_or_fallback():
    # Test fallback resolution
    res = DynamicTaxonomyService.resolve_candidate_role_and_domain(
        role_or_summary="Software Developer",
        skills=["Python", "FastAPI", "PostgreSQL"],
    )
    assert isinstance(res, DynamicTaxonomyResult)
    assert res.domain_name is not None
    assert res.family_name is not None


def test_add_dynamic_designation():
    # Add a brand new designation "Prompt Engineer"
    success = DynamicTaxonomyService.add_designation(
        designation_name="Prompt Engineer",
        family_name="Software Engineering & Development",
        synonyms=["LLM Specialist", "AI Prompt Developer"],
        seniority_level="Senior",
    )
    assert success is True

    # Test resolving newly added designation
    resolved = DynamicTaxonomyService.resolve_candidate_role_and_domain(
        role_or_summary="AI Prompt Developer",
        skills=["Prompting", "LLMs"],
    )
    assert isinstance(resolved, DynamicTaxonomyResult)
    assert resolved.family_name == "Software Engineering & Development"
