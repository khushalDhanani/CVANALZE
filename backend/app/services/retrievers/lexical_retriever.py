from __future__ import annotations
from sqlalchemy import func, select, text

from app.core.database import PostgresAppSession
from app.core.logging import logger
from app.models.pg import CandidateSearchDocument


class LexicalCandidateRetriever:
    """
    Decoupled PostgreSQL Full-Text Search (FTS) & Trigram Candidate Retriever.
    Executes PostgreSQL `tsvector` FTS (`websearch_to_tsquery`) and `pg_trgm` trigram similarity queries inside PostgreSQL.
    Eliminates Python disk file loading and $O(N)$ full table scans.
    """

    @classmethod
    def retrieve_candidates(
        cls,
        query_text: str,
        top_k: int = 200,
    ) -> tuple[dict[str, int], dict[str, float]]:
        """
        Execute PostgreSQL FTS and trigram matching on candidate_search_documents table.
        Returns a tuple of (lexical_ranks_dict, lexical_scores_dict).
        """
        ranks: dict[str, int] = {}
        scores: dict[str, float] = {}

        if not query_text or not query_text.strip() or PostgresAppSession is None:
            return ranks, scores

        clean_query = query_text.strip()

        try:
            with PostgresAppSession() as session:
                # 1. Attempt PostgreSQL websearch_to_tsquery FTS matching
                ts_query = func.websearch_to_tsquery('english', clean_query)
                rank_col = func.ts_rank_cd(CandidateSearchDocument.search_document, ts_query).label("fts_rank")

                stmt = (
                    select(CandidateSearchDocument.cv_key, rank_col)
                    .where(CandidateSearchDocument.search_document.bool_op("@@")(ts_query))
                    .order_by(text("fts_rank DESC"))
                    .limit(top_k)
                )

                rows = session.execute(stmt).all()

                if rows:
                    for rank_idx, r in enumerate(rows, start=1):
                        cv_key = str(r.cv_key)
                        score = float(r.fts_rank) if r.fts_rank is not None else 0.1
                        ranks[cv_key] = rank_idx
                        scores[cv_key] = round(score, 4)
                else:
                    # 2. Fallback to pg_trgm similarity match if FTS returns zero matches
                    trgm_sim = func.similarity(CandidateSearchDocument.content_snapshot, clean_query).label("trgm_sim")
                    stmt_trgm = (
                        select(CandidateSearchDocument.cv_key, trgm_sim)
                        .where(trgm_sim > 0.1)
                        .order_by(text("trgm_sim DESC"))
                        .limit(top_k)
                    )
                    rows_trgm = session.execute(stmt_trgm).all()
                    for rank_idx, r in enumerate(rows_trgm, start=1):
                        cv_key = str(r.cv_key)
                        score = float(r.trgm_sim) if r.trgm_sim is not None else 0.1
                        ranks[cv_key] = rank_idx
                        scores[cv_key] = round(score, 4)

        except Exception as exc:
            logger.warning(f"[LEXICAL_RETRIEVER] FTS/trigram search failed: {exc}")

        return ranks, scores
