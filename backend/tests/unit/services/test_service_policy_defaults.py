from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.core.rule_config_manager import ExtractionPolicy, RetrievalPolicy
from app.services.candidate_domain_service import CandidateDomainService
from app.services.candidate_search_reranker import CandidateSearchReranker
from app.services.candidate_search_service import CandidateSearchService
from app.services.performance_service import LRUMemoryCache
from app.services.retrievers.lexical_retriever import LexicalCandidateRetriever
from app.services.retrievers.structured_retriever import StructuredCandidateRetriever
from app.services.retrievers.vector_retriever import VectorCandidateRetriever
from app.services.search_quality_evaluator import SearchQualityEvaluator
from app.services.vacancy_prefilter import PgVectorQueryCache, VacancyPreFilter


def _assert_default_is_none(callable_object: object, parameter: str) -> None:
    assert inspect.signature(callable_object).parameters[parameter].default is None


def test_retrieval_controls_are_resolved_at_runtime() -> None:
    for callable_object, parameter in (
        (CandidateSearchService._vector_search_pg, "top_k"),
        (CandidateSearchReranker.rerank_retrieved_candidates, "limit"),
        (LexicalCandidateRetriever.retrieve_candidates, "top_k"),
        (StructuredCandidateRetriever.retrieve_candidates, "top_k"),
        (VectorCandidateRetriever.retrieve_candidates, "top_k"),
        (PgVectorQueryCache.query_pgvector_cached, "top_limit"),
        (VacancyPreFilter.vector_prefilter, "top_k"),
        (SearchQualityEvaluator.evaluate_retrieval, "top_k"),
        (SearchQualityEvaluator.evaluate_ann_vs_exact_recall, "top_k"),
    ):
        _assert_default_is_none(callable_object, parameter)


def test_reranking_thresholds_are_resolved_at_runtime() -> None:
    _assert_default_is_none(
        CandidateSearchReranker.rerank_retrieved_candidates, "high_threshold"
    )
    _assert_default_is_none(
        CandidateSearchReranker.rerank_retrieved_candidates, "potential_threshold"
    )


def test_cache_and_domain_confidence_defaults_are_policy_backed() -> None:
    _assert_default_is_none(LRUMemoryCache, "default_ttl")
    _assert_default_is_none(CandidateDomainService.validate_skills, "source_confidence")
    assert ExtractionPolicy().default_skill_source_confidence == 0.45


def test_retrieval_and_recovery_controls_have_typed_configuration() -> None:
    policy = RetrievalPolicy()
    assert policy.search_quality_top_k >= 1
    assert policy.vector_candidate_pool >= policy.rerank_top_n
    assert settings.PROCESSING_RECOVERY_LOCK_TIMEOUT_SECONDS > 0
    assert settings.PROCESSING_RECOVERY_LOCK_BLOCKING_TIMEOUT_SECONDS >= 0


def test_retrieval_policy_rejects_invalid_weight_totals() -> None:
    with pytest.raises(ValidationError):
        RetrievalPolicy(rerank_retrieval_weight=0.8, rerank_qualitative_weight=0.8)

    with pytest.raises(ValidationError):
        RetrievalPolicy(section_weights={"skills": 0.0})
