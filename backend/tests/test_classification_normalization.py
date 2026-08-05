"""Tests for classification normalization — NormalizedClassification, DepartmentNormalizer."""
import pytest

from app.schemas.classification_types import (
    AISuggestion,
    ClassificationEvidence,
    NormalizedClassification,
)


class TestNormalizedClassification:
    def test_db_match_creation(self):
        nc = NormalizedClassification(
            db_department_id=9,
            db_department_name="CIS Team",
            db_designation_id=1,
            db_designation_name="Sr. Developer (.NET)",
            industry_department="Information Technology",
            industry_designation="Senior Developer .Net",
            industry_domain="IT & Software Services",
            match_status="DB_MATCH",
            confidence=0.95,
            evidence=[
                ClassificationEvidence(
                    source="mssql_exact",
                    matched_term="sr. developer",
                    matched_against="Sr. Developer (.NET)",
                    confidence=1.0,
                )
            ],
        )
        assert nc.match_status == "DB_MATCH"
        assert nc.confidence == 0.95
        assert nc.db_department_name == "CIS Team"
        assert nc.industry_department == "Information Technology"
        assert len(nc.evidence) == 1

    def test_no_suitable_match_creation(self):
        nc = NormalizedClassification(
            match_status="NO_SUITABLE_MATCH",
            confidence=0.0,
        )
        assert nc.db_department_id is None
        assert nc.industry_department is None
        assert nc.ai_career_suggestion is None

    def test_ai_suggestion_attached(self):
        suggestion = AISuggestion(
            suggested_role="Plant Maintenance Engineer",
            suggested_domain="Plant & Maintenance Engineering",
            confidence=0.5,
            missing_requirements=["No active vacancy for this domain"],
        )
        nc = NormalizedClassification(
            match_status="NO_SUITABLE_MATCH",
            confidence=0.0,
            ai_career_suggestion=suggestion,
        )
        assert nc.ai_career_suggestion is not None
        assert nc.ai_career_suggestion.suggested_role == "Plant Maintenance Engineer"

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            ClassificationEvidence(
                source="test",
                matched_term="x",
                matched_against="y",
                confidence=1.5,  # out of bounds
            )


class TestDepartmentNormalizer:
    """Unit tests for DepartmentNormalizer without hitting a live DB (cache miss path)."""

    def test_normalize_department_empty(self):
        from app.services.department_normalizer import DepartmentNormalizer
        result = DepartmentNormalizer.normalize_department(None)
        assert result["industry_department"] is None

    def test_normalize_department_empty_string(self):
        from app.services.department_normalizer import DepartmentNormalizer
        result = DepartmentNormalizer.normalize_department("")
        assert result["industry_department"] is None

    def test_normalize_designation_empty(self):
        from app.services.department_normalizer import DepartmentNormalizer
        result = DepartmentNormalizer.normalize_designation(None)
        assert result["industry_designation"] is None

    def test_normalize_designation_sr_expansion(self):
        from app.services.department_normalizer import DepartmentNormalizer
        # Force cache miss by testing a term not in cache
        DepartmentNormalizer._cache.clear()
        result = DepartmentNormalizer.normalize_designation("Sr. Developer (.NET)")
        assert result["industry_designation"] is not None
        assert "Senior" in result["industry_designation"]

    def test_normalize_designation_jr_expansion(self):
        from app.services.department_normalizer import DepartmentNormalizer
        DepartmentNormalizer._cache.clear()
        result = DepartmentNormalizer.normalize_designation("Jr. Technician")
        assert "Junior" in result["industry_designation"]


class TestSeedIndustryLabels:
    """Verify every active seed entry has an industry_label."""

    def test_all_active_entries_have_industry_label(self):
        import json
        import os
        seed_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "data", "department_domains_seed.json"
        )
        with open(seed_path, "r", encoding="utf-8") as f:
            seed = json.load(f)
        for entry in seed.get("domains", []):
            if entry.get("is_active"):
                assert "industry_label" in entry, (
                    f"Active entry '{entry.get('department_name')}' missing industry_label"
                )
                assert entry["industry_label"], (
                    f"Active entry '{entry.get('department_name')}' has empty industry_label"
                )

    def test_cis_team_no_broad_keywords(self):
        import json
        import os
        seed_path = os.path.join(
            os.path.dirname(__file__), "..", "app", "data", "department_domains_seed.json"
        )
        with open(seed_path, "r", encoding="utf-8") as f:
            seed = json.load(f)
        cis = next(
            (d for d in seed.get("domains", []) if d.get("department_name") == "CIS Team"),
            None,
        )
        assert cis is not None, "CIS Team entry not found in seed"
        broad_keywords = {"sql", "api", "code", "coding", "web", "database"}
        cis_keywords = {k.lower() for k in cis.get("keywords", [])}
        overlap = broad_keywords & cis_keywords
        assert not overlap, f"CIS Team still has broad keywords: {overlap}"
