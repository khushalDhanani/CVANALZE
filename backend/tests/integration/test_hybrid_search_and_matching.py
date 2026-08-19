from __future__ import annotations

from app.services.rank_fusion_service import RankFusionService
from app.services.scoring_engine import ScoringEngine


def test_hybrid_search_and_matching_flow(
    sample_candidate_cv_text: str,
    sample_job_openings: list[dict],
) -> None:
    # 1. Candidate domain profile extraction
    domain_profile = ScoringEngine.extract_candidate_domain_profile(sample_candidate_cv_text)
    assert domain_profile is not None

    # 2. Hybrid RRF rank fusion across retrieval sources
    vector_rankings = {"cand_1": 1, "cand_2": 2, "cand_3": 3}
    lexical_rankings = {"cand_1": 1, "cand_3": 2, "cand_2": 3}

    fused_results = RankFusionService.fuse_rankings(
        vector_ranks=vector_rankings,
        lexical_ranks=lexical_rankings,
        k_constant=60.0,
    )

    assert len(fused_results) == 3
    # Candidate 1 is top in both vector and lexical, should have the highest RRF score
    assert fused_results[0].cv_key == "cand_1"
