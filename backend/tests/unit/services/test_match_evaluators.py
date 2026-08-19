from __future__ import annotations

from app.schemas.match import RequirementStatus, RequirementTier
from app.services.match_evaluators import is_ignorable_requirement


def test_is_ignorable_requirement_artifacts() -> None:
    # Empty or whitespace strings are ignorable artifacts
    assert is_ignorable_requirement("") is True
    assert is_ignorable_requirement("   ") is True

    # Generic years clauses are ignorable as skill requirements
    assert is_ignorable_requirement("3+ years experience") is True
    assert is_ignorable_requirement("5 to 7 years") is True

    # Sentence prose fragments are ignorable
    assert is_ignorable_requirement("Candidate should possess good attitude. Needs to work well.") is True
    assert is_ignorable_requirement("This is a long generic sentence describing job requirements in detail") is True

    # Real skills are NOT ignorable
    assert is_ignorable_requirement("Python") is False
    assert is_ignorable_requirement("FastAPI") is False
    assert is_ignorable_requirement("Docker") is False
    assert is_ignorable_requirement("PostgreSQL") is False
