from __future__ import annotations

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
