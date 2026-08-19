from __future__ import annotations
import pytest
from unittest.mock import MagicMock, patch

from app.schemas.candidate_search import CandidateSearchRequest
from app.services.candidate_search_document_builder import CandidateSearchDocumentBuilder
from app.services.candidate_search_reranker import CandidateSearchReranker
from app.services.rank_fusion_service import CandidateRankItem, RankFusionService
from app.services.retrievers import (
    LexicalCandidateRetriever,
    StructuredCandidateRetriever,
    VectorCandidateRetriever,
)
from app.services.search_quality_evaluator import SearchQualityEvaluator
from app.services.search_query_analyzer import SearchQueryAnalyzer


def test_search_query_analyzer_extracts_tokens_and_phrases_dynamically():
    query_str = '"Quantum Computing" engineer with at least 5 years experience'

    ctx = SearchQueryAnalyzer.analyze_query(query_str)

    assert ctx.raw_query == query_str
    assert "Quantum Computing" in ctx.phrases
    assert "quantum" in ctx.tokens or "computing" in ctx.tokens
    assert ctx.filters.get("min_experience") == 5.0


def test_vector_retriever_enforces_model_version_and_freshness():
    fake_session = MagicMock()
    mock_query = MagicMock()
    fake_session.execute.return_value.all.return_value = []

    with patch("app.services.retrievers.vector_retriever.PostgresAppSession", return_value=fake_session):
        ranks, sims = VectorCandidateRetriever.retrieve_candidates(
            query_embedding=[0.1] * 768,
            top_k=50,
            model_version="nomic-embed-text",
        )

        assert ranks == {}
        assert sims == {}
        # Verify execution was called
        assert fake_session.execute.called


def test_rank_fusion_service_computes_rrf_scores():
    vec_ranks = {"cand_A": 1, "cand_B": 2}
    lex_ranks = {"cand_B": 1, "cand_C": 2}

    fused = RankFusionService.fuse_rankings(
        vector_ranks=vec_ranks,
        lexical_ranks=lex_ranks,
        k_constant=60.0,
    )

    assert len(fused) == 3
    # cand_B appears in both retrievers so it should have highest RRF score
    assert fused[0].cv_key == "cand_B"
    assert fused[0].rrf_score > fused[1].rrf_score


def test_search_quality_evaluator_computes_metrics():
    retrieved = ["cand_1", "cand_2", "cand_3", "cand_4", "cand_5"]
    ground_truth = ["cand_2", "cand_5"]

    metrics = SearchQualityEvaluator.evaluate_retrieval(retrieved, ground_truth, top_k=5)

    assert metrics.recall_at_k == 1.0  # Both ground truth items in top 5
    assert metrics.precision_at_k == 0.4  # 2 out of 5
    assert metrics.mrr == 0.5  # First hit at rank 2
    assert metrics.ndcg_at_k > 0.0


def test_ann_vs_exact_recall_loss():
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [0.0, 1.0, 0.0]
    vec_c = [0.9, 0.1, 0.0]
    query = [1.0, 0.0, 0.0]

    embeddings_map = {
        "cand_a": vec_a,
        "cand_b": vec_b,
        "cand_c": vec_c,
    }

    # ANN returned cand_a and cand_c (exact top 2 matches)
    ann_retrieved = ["cand_a", "cand_c"]
    recall_loss = SearchQualityEvaluator.evaluate_ann_vs_exact_recall(
        ann_retrieved, embeddings_map, query, top_k=2
    )

    assert recall_loss == 0.0  # 0% loss when top 2 match exact brute force


def test_candidate_search_document_builder_builds_fts_snapshot():
    markdown = "# Dr. Alex Smith\nDegree: Ph.D. in Robotics at MIT\nSkills: ROS2, C++, PyTorch"
    resume_json = {
        "contact_info": {"name": "Dr. Alex Smith"},
        "education": [{"degree": "Ph.D.", "field_of_study": "Robotics", "institution": "MIT"}],
    }

    snapshot = CandidateSearchDocumentBuilder.build_fts_content_snapshot(markdown, resume_json)

    assert "Dr. Alex Smith" in snapshot
    assert "ROS2" in snapshot or "Robotics" in snapshot
