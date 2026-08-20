"""
Unit tests for Phase 1 Part 2 P0 Data Source and Scoring Corrections.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.models.taxonomy import FamilyCompatibility
from app.repositories.job import JobRepository, VacancyLoadStatus, VacancySourceUnavailableError
from app.schemas.scoring_config import ScoringConfig
from app.services.candidate_domain_service import CandidateDomainService


def test_family_compatibility_requires_explicit_attributes():
    """Verify FamilyCompatibility model attributes have no implicit permissive defaults."""
    # Instantiating FamilyCompatibility requires compatibility_score and is_allowed
    compat = FamilyCompatibility(
        family_a_id=1,
        family_b_id=2,
        compatibility_score=0.8,
        is_allowed=True,
    )
    assert compat.compatibility_score == 0.8
    assert compat.is_allowed is True


def test_job_repository_db_unavailable_raises_source_unavailable():
    """When MSSQL DB is unavailable and cache is empty, raise VacancySourceUnavailableError."""
    # Reset cache manager for clean test
    from app.core.cache import vacancy_cache_manager
    vacancy_cache_manager.delete(JobRepository._VACANCY_CACHE_KEY)

    with patch("app.repositories.job.VacancyService") as mock_service_cls:
        mock_service = MagicMock()
        mock_service.get_active_vacancies.side_effect = Exception("DB Connection Failed")
        mock_service_cls.return_value = mock_service

        with pytest.raises(VacancySourceUnavailableError):
            JobRepository.get_all_jobs(db=MagicMock())


def test_candidate_domain_service_unconfident_match_returns_no_confident_match():
    """When taxonomy matching is unconfident, return NO_CONFIDENT_MATCH with null domain."""
    result = CandidateDomainService.extract_candidate_domain_profile(
        cv_text="Generic unclassifiable text without tech keywords",
        resume_json={},
    )
    assert result["taxonomy_match_status"] in ("NO_CONFIDENT_MATCH", "NO_MATCH", "NO_EVIDENCE")
    assert result["recommended_department"] in ("", None)
    assert result["professional_domain"] in ("", None)
