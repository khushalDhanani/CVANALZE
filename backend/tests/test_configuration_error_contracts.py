import pytest

from app.api.candidates import list_candidates, search_candidates_post
from app.core.error_handlers import SystemConfigurationError
from app.schemas.candidate_search import CandidateSearchRequest
from app.services.candidate_search_service import CandidateSearchService


def test_candidate_search_preserves_configuration_unavailable(monkeypatch):
    def fail_for_missing_config(_request):
        raise SystemConfigurationError("CONFIGURATION_UNAVAILABLE")

    monkeypatch.setattr(CandidateSearchService, "search_candidates", fail_for_missing_config)

    with pytest.raises(SystemConfigurationError, match="CONFIGURATION_UNAVAILABLE"):
        search_candidates_post(CandidateSearchRequest())


def test_candidate_list_preserves_configuration_unavailable(monkeypatch):
    def fail_for_missing_config(_request):
        raise SystemConfigurationError("CONFIGURATION_UNAVAILABLE")

    monkeypatch.setattr(CandidateSearchService, "search_candidates", fail_for_missing_config)

    with pytest.raises(SystemConfigurationError, match="CONFIGURATION_UNAVAILABLE"):
        list_candidates(
            search=None,
            query=None,
            department=None,
            min_experience=None,
            max_experience=None,
            location=None,
            skills=None,
            education=None,
            status=None,
            min_similarity=None,
            limit=50,
        )
