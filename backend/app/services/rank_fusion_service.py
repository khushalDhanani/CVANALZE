from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.logging import logger


@dataclass
class CandidateRankItem:
    """
    Represents a candidate item scored and ranked via Reciprocal Rank Fusion.
    """
    cv_key: str
    rrf_score: float
    vector_rank: int | None = None
    lexical_rank: int | None = None
    structured_rank: int | None = None
    vector_similarity: float | None = None
    lexical_score: float | None = None
    retrieval_sources: list[str] = field(default_factory=list)


class RankFusionService:
    """
    Domain-agnostic Reciprocal Rank Fusion (RRF) Service.
    Fuses candidate rankings from distinct retrieval sources (Vector, Lexical FTS, Structured)
    using RRF score = sum(weight_m / (k + rank_m)).
    Does NOT depend on specific domain terms, skills, or technologies.
    """

    @classmethod
    def fuse_rankings(
        cls,
        vector_ranks: dict[str, int] | None = None,
        lexical_ranks: dict[str, int] | None = None,
        structured_ranks: dict[str, int] | None = None,
        vector_similarities: dict[str, float] | None = None,
        lexical_scores: dict[str, float] | None = None,
        k_constant: float | None = None,
        weights: dict[str, float] | None = None,
    ) -> list[CandidateRankItem]:
        """
        Fuse multiple candidate rank maps into a single unified RRF-ranked list.
        """
        k = k_constant if k_constant is not None else getattr(settings, "RRF_K_CONSTANT", 60.0)
        vec_map = vector_ranks or {}
        lex_map = lexical_ranks or {}
        struct_map = structured_ranks or {}
        vec_sims = vector_similarities or {}
        lex_sims = lexical_scores or {}

        source_weights = weights or {
            "vector": 1.0,
            "lexical": 1.0,
            "structured": 1.0,
        }

        all_keys: set[str] = set().union(vec_map.keys(), lex_map.keys(), struct_map.keys())

        scored_items: list[CandidateRankItem] = []

        for cv_key in all_keys:
            rrf_score = 0.0
            sources: list[str] = []

            v_rank = vec_map.get(cv_key)
            if v_rank is not None and v_rank > 0:
                rrf_score += source_weights.get("vector", 1.0) / (k + v_rank)
                sources.append("vector")

            l_rank = lex_map.get(cv_key)
            if l_rank is not None and l_rank > 0:
                rrf_score += source_weights.get("lexical", 1.0) / (k + l_rank)
                sources.append("lexical")

            s_rank = struct_map.get(cv_key)
            if s_rank is not None and s_rank > 0:
                rrf_score += source_weights.get("structured", 1.0) / (k + s_rank)
                sources.append("structured")

            item = CandidateRankItem(
                cv_key=cv_key,
                rrf_score=round(rrf_score, 6),
                vector_rank=v_rank,
                lexical_rank=l_rank,
                structured_rank=s_rank,
                vector_similarity=vec_sims.get(cv_key),
                lexical_score=lex_sims.get(cv_key),
                retrieval_sources=sources,
            )
            scored_items.append(item)

        scored_items.sort(key=lambda x: (-x.rrf_score, x.cv_key))
        return scored_items
