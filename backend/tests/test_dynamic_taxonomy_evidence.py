"""Tests for DynamicTaxonomyService evidence production and NormalizedClassification output."""
import pytest

from app.schemas.classification_types import NormalizedClassification


class TestDynamicTaxonomyFallback:
    """Tests for the fallback path (no DB, no pgvector) — always exercisable in CI."""

    def test_fallback_returns_no_suitable_match(self):
        from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
        # Empty input should use fallback
        result = DynamicTaxonomyService._get_default_fallback(matched_term="unknown role")
        assert isinstance(result, NormalizedClassification)
        assert result.match_status == "NO_SUITABLE_MATCH"
        assert result.confidence == 0.0
        assert result.match_source == "legacy_fallback"

    def test_fallback_has_evidence(self):
        from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
        result = DynamicTaxonomyService._get_default_fallback(matched_term="chef")
        assert len(result.evidence) > 0
        ev = result.evidence[0]
        assert ev.source == "fallback"
        assert ev.matched_term == "chef"
        assert ev.confidence == 0.0

    def test_fallback_evidence_matched_against_is_none(self):
        from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
        result = DynamicTaxonomyService._get_default_fallback()
        assert result.evidence[0].matched_against is None

    def test_empty_input_uses_fallback(self):
        from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
        result = DynamicTaxonomyService.resolve_candidate_role_and_domain(role_or_summary="")
        assert isinstance(result, NormalizedClassification)
        assert result.match_status == "NO_SUITABLE_MATCH"

    def test_result_has_correct_fields(self):
        from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
        result = DynamicTaxonomyService.resolve_candidate_role_and_domain(
            role_or_summary="some unknown role xyz",
        )
        # Verify schema fields exist
        assert hasattr(result, "db_department_id")
        assert hasattr(result, "db_department_name")
        assert hasattr(result, "db_designation_id")
        assert hasattr(result, "db_designation_name")
        assert hasattr(result, "industry_department")
        assert hasattr(result, "industry_designation")
        assert hasattr(result, "industry_domain")
        assert hasattr(result, "match_status")
        assert hasattr(result, "confidence")
        assert hasattr(result, "evidence")
        assert hasattr(result, "match_source")


class TestJobTaxonomyFieldCompatibility:
    """Verify job_taxonomy.py reads correct NormalizedClassification fields (no AttributeError)."""

    def test_classify_vacancy_dto_does_not_crash(self):
        """Ensure classify_vacancy_dto succeeds with an unknown title (triggers fallback path)."""
        from app.services.job_taxonomy import TaxonomyClassifier, VacancyDTO
        dto = VacancyDTO(
            id="test",
            title="Highly Unusual Nonexistent Role 99999",
            title_lower="highly unusual nonexistent role 99999",
            department="Unknown",
            department_lower="unknown",
            normalized_job_text="highly unusual nonexistent role 99999 unknown",
        )
        result = TaxonomyClassifier.classify_vacancy_dto(dto)
        # Must not raise AttributeError
        assert result.domain is not None
        assert result.job_family is not None

    def test_classify_candidate_dto_does_not_crash(self):
        from app.services.job_taxonomy import TaxonomyClassifier, CandidateResumeDTO
        dto = CandidateResumeDTO(
            cv_text="I am an underwater basket weaver with 10 years of experience.",
            summary="Underwater basket weaver",
            experience_titles=["Underwater basket weaver"],
            normalized_full_text="underwater basket weaver 10 years experience",
        )
        result = TaxonomyClassifier.classify_candidate_dto(dto)
        assert result.domain is not None
        assert result.job_family is not None
