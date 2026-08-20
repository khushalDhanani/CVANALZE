from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import patch

from app.core.config import settings
from app.schemas.candidate_search import CandidateSearchRequest
from app.services.candidate_search_service import CandidateSearchService
from app.services.embedding_service import EmbeddingService
from app.services.rank_fusion_service import CandidateRankItem, RankFusionService
from app.services.search_query_analyzer import SearchQueryAnalyzer


def test_rank_fusion_service_fuses_ranks() -> None:
    # Candidate A is #1 in vector (rank 1), #2 in lexical (rank 2)
    # Candidate B is #2 in vector (rank 2), #1 in lexical (rank 1)
    # Candidate C is only in vector (rank 3)
    vector_ranks = {"cand_A": 1, "cand_B": 2, "cand_C": 3}
    lexical_ranks = {"cand_A": 2, "cand_B": 1}

    fused = RankFusionService.fuse_rankings(
        vector_ranks=vector_ranks,
        lexical_ranks=lexical_ranks,
        k_constant=60.0,
    )

    assert len(fused) == 3
    assert all(isinstance(item, CandidateRankItem) for item in fused)
    # A and B should both have higher scores than C
    scores = {item.cv_key: item.rrf_score for item in fused}
    assert scores["cand_A"] > scores["cand_C"]
    assert scores["cand_B"] > scores["cand_C"]


def test_search_query_analyzer_extracts_tokens() -> None:
    query = "Senior Python Developer with FastAPI and PostgreSQL in San Francisco"
    analysis = SearchQueryAnalyzer.analyze_query(query)
    assert analysis is not None
    assert analysis.raw_query == query
    assert len(analysis.tokens) > 0


def test_embedding_failure_throttle_uses_runtime_setting(monkeypatch) -> None:
    monkeypatch.setattr(settings, "OLLAMA_CIRCUIT_BREAKER_RESET_SECONDS", 7.0)
    EmbeddingService._failed_models_cache["test-model"] = time.time() - 8.0

    try:
        assert EmbeddingService._is_model_throttled("test-model") is False
    finally:
        EmbeddingService._failed_models_cache.pop("test-model", None)


def test_candidate_search_uses_policy_retrieval_pool() -> None:
    policy_snapshot = SimpleNamespace(
        retrieval=SimpleNamespace(vector_candidate_pool=37, rrf_k=71.0),
    )

    with (
        patch("app.core.rule_config_manager.PolicyRegistry.resolve_snapshot", return_value=policy_snapshot),
        patch(
            "app.services.retrievers.StructuredCandidateRetriever.retrieve_candidates",
            return_value={},
        ) as structured_retrieve,
        patch("app.repositories.result.ResultRepository.list_all_results", return_value=[]),
        patch(
            "app.services.candidate_search_reranker.CandidateSearchReranker.rerank_retrieved_candidates",
            return_value=[],
        ),
    ):
        response = CandidateSearchService.search_candidates(
            CandidateSearchRequest(department="Engineering"),
        )

    structured_retrieve.assert_called_once()
    assert structured_retrieve.call_args.kwargs["top_k"] == 37
    assert response.candidates == []
