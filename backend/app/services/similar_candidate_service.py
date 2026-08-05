from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.repositories.result import ResultRepository
from app.services.embedding_service import EmbeddingService, get_candidate_embedding


class SimilarCandidateService:
    """
    Service for automatic detection of similar or duplicate candidate profiles.
    Compares candidate vector embeddings using cosine similarity against existing candidates,
    flags highly similar profiles (>= 0.85 similarity), and marks potential duplicates (>= 0.95).
    Does NOT auto-merge or modify original candidate records.
    """

    @classmethod
    def _vector_search_pg(cls, target_cv_key: str, cv_embedding: list[float], limit: int) -> dict[str, float]:
        scores: dict[str, float] = {}
        try:
            from app.core.database import PostgresAppSession
            from app.models.pg import CandidateEmbedding

            if PostgresAppSession is not None:
                with PostgresAppSession() as session:
                    stmt = (
                        select(
                            CandidateEmbedding.cv_key,
                            CandidateEmbedding.embedding.cosine_distance(cv_embedding).label("distance"),
                        )
                        .where(CandidateEmbedding.cv_key != target_cv_key)
                        .order_by("distance")
                        .limit(limit)
                    )
                    rows = session.execute(stmt).all()
                    for r in rows:
                        other_key = str(r.cv_key)
                        dist = float(r.distance) if r.distance is not None else 1.0
                        sim = round(max(0.0, 1.0 - dist), 4)
                        scores[other_key] = sim
        except Exception as exc:
            logger.warning(f"[SIMILAR_CANDIDATES] pgvector search failed: {exc}")

        return scores

    @classmethod
    def detect_similar_candidates(
        cls,
        cv_key: str,
        cv_embedding: list[float] | None = None,
        threshold: float | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if not cv_embedding or not settings.EMBEDDING_ENABLED:
            return []

        thresh = threshold if threshold is not None else settings.SIMILAR_CANDIDATE_THRESHOLD
        max_matches = limit if limit is not None else settings.SIMILAR_CANDIDATE_MAX_MATCHES

        vector_scores = cls._vector_search_pg(cv_key, cv_embedding, limit=max_matches * 3)

        # Optimize: If pgvector returned matches, only resolve results for those keys rather than reading all disk files
        if vector_scores:
            target_keys = list(vector_scores.keys())
            candidate_records = []
            for k in target_keys:
                rec = ResultRepository.resolve_result(k)
                if rec and isinstance(rec, dict):
                    candidate_records.append(rec)
        else:
            candidate_records = ResultRepository.list_all_results()

        similar_candidates: list[dict[str, Any]] = []

        for r in candidate_records:
            if not r or not isinstance(r, dict):
                continue

            other_key = str(r.get("id") or r.get("filename") or "")
            other_key = other_key.removesuffix(".json")

            # Skip comparing candidate against itself
            if other_key == cv_key:
                continue

            sim_score: float | None = vector_scores.get(other_key)

            # Fallback to cache lookup if pgvector search returned no score for this candidate
            if sim_score is None:
                other_emb = get_candidate_embedding(other_key)
                if other_emb is not None:
                    sim_score = round(EmbeddingService.cosine_similarity(cv_embedding, other_emb), 4)

            if sim_score is None or sim_score < thresh:
                continue

            raw_match = r.get("match_analysis")
            match_analysis = raw_match if isinstance(raw_match, dict) else {}
            best_match = match_analysis.get("best_match") or {}

            resume_json = r.get("resume_json") or {}
            contact_info = resume_json.get("contact_info") or {}
            extracted_name = contact_info.get("name") or contact_info.get("full_name")
            email = contact_info.get("email")
            phone = contact_info.get("phone")

            similar_item = {
                "cv_key": other_key,
                "candidate_id": r.get("candidate_id") or other_key,
                "filename": r.get("filename") or f"{other_key}.pdf",
                "full_name": extracted_name if extracted_name else None,
                "email": email if email else None,
                "phone": phone if phone else None,
                "primary_department": match_analysis.get("primary_department") or best_match.get("department"),
                "best_match_title": best_match.get("job_title"),
                "similarity_score": sim_score,
                "is_duplicate_flag": sim_score >= 0.95,
                "parsed_at": r.get("parsed_at") or r.get("created_at"),
            }
            similar_candidates.append(similar_item)

        # Sort descending by similarity score
        similar_candidates.sort(key=lambda x: x.get("similarity_score", 0.0), reverse=True)
        top_similar = similar_candidates[:max_matches]

        if top_similar:
            logger.info(f"[SIMILAR_CANDIDATES] Detected {len(top_similar)} similar candidate profile(s) for '{cv_key}' (Top similarity: {top_similar[0]['similarity_score']}, Threshold: {thresh}).")

        return top_similar
