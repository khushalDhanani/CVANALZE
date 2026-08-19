from __future__ import annotations
from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import PostgresAppSession
from app.core.logging import logger
from app.models.pg import CandidateEmbedding, CandidateSectionEmbedding


class VectorCandidateRetriever:
    """
    Decoupled PGVector Candidate Retriever.
    Queries section vector embeddings (or candidate composite vector) while strictly enforcing:
    - embedding IS NOT NULL
    - freshness_status = 'FRESH'
    - embedding_model_version = current configured model
    Dynamically applies `SET LOCAL hnsw.ef_search` for configurable query-time HNSW recall tuning.
    """

    @classmethod
    def retrieve_candidates(
        cls,
        query_embedding: list[float],
        top_k: int = 200,
        section_type: str | None = None,
        model_version: str | None = None,
    ) -> tuple[dict[str, int], dict[str, float]]:
        """
        Execute safe PGVector cosine distance search against candidate section vectors or composite vectors.
        Returns a tuple of (vector_ranks_dict, vector_similarities_dict).
        """
        ranks: dict[str, int] = {}
        similarities: dict[str, float] = {}

        if not query_embedding or not settings.EMBEDDING_ENABLED or PostgresAppSession is None:
            return ranks, similarities

        target_model = model_version or settings.EMBEDDING_MODEL
        ef_search = getattr(settings, "HNSW_EF_SEARCH", 100)

        try:
            with PostgresAppSession() as session:
                # Apply configurable query-time HNSW ef_search tuning
                try:
                    session.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef_search)}"))
                except Exception as ef_exc:
                    logger.debug(f"[VECTOR_RETRIEVER] Could not set hnsw.ef_search: {ef_exc}")

                section = (section_type or "").lower().strip()

                if section and section != "overall":
                    # Query candidate_section_embeddings with model version & freshness guards
                    stmt = (
                        select(
                            CandidateSectionEmbedding.cv_key,
                            CandidateSectionEmbedding.embedding.cosine_distance(query_embedding).label("distance"),
                        )
                        .where(CandidateSectionEmbedding.embedding.isnot(None))
                        .where(CandidateSectionEmbedding.freshness_status == "FRESH")
                        .where(CandidateSectionEmbedding.embedding_model_version == target_model)
                        .where(CandidateSectionEmbedding.section_type == section)
                        .order_by("distance")
                        .limit(top_k)
                    )
                    rows = session.execute(stmt).all()

                    for rank_idx, r in enumerate(rows, start=1):
                        cv_key = str(r.cv_key)
                        dist = float(r.distance) if r.distance is not None else 1.0
                        sim = round(max(0.0, 1.0 - dist), 4)
                        ranks[cv_key] = rank_idx
                        similarities[cv_key] = sim
                else:
                    # Fallback to candidate_embeddings table with model version & freshness guards
                    stmt = (
                        select(
                            CandidateEmbedding.cv_key,
                            CandidateEmbedding.embedding.cosine_distance(query_embedding).label("distance"),
                        )
                        .where(CandidateEmbedding.embedding.isnot(None))
                        .where(CandidateEmbedding.freshness_status == "FRESH")
                        .where(CandidateEmbedding.embedding_model_version == target_model)
                        .order_by("distance")
                        .limit(top_k)
                    )
                    rows = session.execute(stmt).all()

                    for rank_idx, r in enumerate(rows, start=1):
                        cv_key = str(r.cv_key)
                        dist = float(r.distance) if r.distance is not None else 1.0
                        sim = round(max(0.0, 1.0 - dist), 4)
                        ranks[cv_key] = rank_idx
                        similarities[cv_key] = sim

        except Exception as exc:
            logger.warning(f"[VECTOR_RETRIEVER] Vector search failed: {exc}")

        return ranks, similarities
