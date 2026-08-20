from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.domain_knowledge import (
    DomainEquivalentRequest,
    ResolveRoleRequest,
    get_semantic_equivalents,
    resolve_role_dynamically,
)
from app.core.rule_config_manager import SimilarityPolicy


def _snapshot() -> SimpleNamespace:
    return SimpleNamespace(
        similarity=SimilarityPolicy(
            min_similarity_threshold=0.40,
            domain_default_threshold=0.60,
            role_resolution_threshold=0.55,
            domain_default_limit=7,
            domain_max_limit=8,
        )
    )


def test_equivalent_defaults_resolve_from_similarity_policy(monkeypatch) -> None:
    finder = Mock(return_value=[])
    monkeypatch.setattr("app.api.domain_knowledge.PolicyRegistry.resolve_snapshot", _snapshot)
    monkeypatch.setattr("app.api.domain_knowledge.DomainEmbeddingService.CATEGORIES", {"skills"})
    monkeypatch.setattr("app.api.domain_knowledge.DomainEmbeddingService.find_semantic_equivalents", finder)

    response = get_semantic_equivalents(DomainEquivalentRequest(term="Postgres", category="skills"))

    assert response.equivalents == []
    finder.assert_called_once_with(term="Postgres", category="skills", threshold=0.60, limit=7)


def test_equivalent_request_is_bounded_by_active_policy(monkeypatch) -> None:
    monkeypatch.setattr("app.api.domain_knowledge.PolicyRegistry.resolve_snapshot", _snapshot)
    monkeypatch.setattr("app.api.domain_knowledge.DomainEmbeddingService.CATEGORIES", {"skills"})

    with pytest.raises(HTTPException) as exc_info:
        get_semantic_equivalents(
            DomainEquivalentRequest(term="Postgres", category="skills", threshold=0.30)
        )

    assert exc_info.value.status_code == 422


def test_role_resolution_default_resolves_from_similarity_policy(monkeypatch) -> None:
    resolver = Mock(return_value={"status": "resolved"})
    monkeypatch.setattr("app.api.domain_knowledge.PolicyRegistry.resolve_snapshot", _snapshot)
    monkeypatch.setattr("app.api.domain_knowledge.DynamicTaxonomyService.resolve_candidate_role_and_domain", resolver)

    result = resolve_role_dynamically(ResolveRoleRequest(role_or_summary="Engineer"))

    assert result == {"status": "resolved"}
    resolver.assert_called_once_with(role_or_summary="Engineer", skills=[], threshold=0.55)
