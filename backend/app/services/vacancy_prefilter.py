import hashlib
import re
from typing import Any

from app.core.cache import embedding_cache_manager
from app.core.config import settings
from app.core.logging import logger
from app.services.embedding_service import EmbeddingService


class VacancyPreFilter:
    """
    Lightweight deterministic Python pre-filter to narrow down active database vacancies
    to the top relevant candidates before passing them to the LLM.
    Uses Reciprocal Rank Fusion (RRF) to merge lexical and pgvector semantic ranks.
    """

    @classmethod
    def vector_prefilter(cls, candidate_embedding: list[float], top_k: int = 200) -> dict[str, int]:
        """
        Executes a pgvector cosine distance query against PostgreSQL.
        Returns a dict mapping vacancy_id (str) to its vector rank (1-indexed).
        """
        ranks = {}
        try:
            from app.core.database import pg_SessionLocal
            from app.models.pg import VacancyEmbedding
            from sqlalchemy import select

            with pg_SessionLocal() as session:
                # Get vector distance for all embedded vacancies ordered by proximity
                stmt = select(VacancyEmbedding.vacancy_id) \
                       .order_by(VacancyEmbedding.embedding.cosine_distance(candidate_embedding)) \
                       .limit(top_k)
                results = session.execute(stmt).scalars().all()
                for rank, vid in enumerate(results, 1):
                    ranks[str(vid)] = rank
        except Exception as e:
            logger.warning(f"Vector pre-filter failed: {e}")
        return ranks

    @classmethod
    def filter_vacancies(
        cls,
        cv_text: str,
        openings: list[dict[str, Any]],
        candidate_experience: float | None = None,
        top_k: int | None = None,
        cv_embedding: list[float] | None = None,
    ) -> list[dict[str, Any]]:
        if not openings:
            return []

        limit = top_k or settings.PREFILTER_TOP_K
        if len(openings) <= limit:
            return openings

        cv_lower = cv_text.lower()
        stop_words = {"and", "team", "for", "the", "with", "senior", "junior", "lead", "manager", "developer", "engineer", "specialist"}

        # Generate cv_embedding if missing
        if cv_embedding is None and settings.EMBEDDING_ENABLED:
            try:
                cv_embedding = EmbeddingService.generate_embedding(
                    cv_text[:8000], settings.EMBEDDING_MODEL
                )
            except Exception as e:
                logger.warning(f"CV embedding generation failed in prefilter: {e}")
                cv_embedding = None

        # 1. Fetch Vector Ranks (pgvector)
        vec_ranks = {}
        if cv_embedding:
            # fetch up to len(openings) so we rank as many as possible
            vec_ranks = cls.vector_prefilter(cv_embedding, top_k=max(200, len(openings)))

        # 2. Compute Lexical Scores & Ranks
        lexical_scored = []
        for job in openings:
            score = 0.0

            # Department match
            dept_name = job.get("_precomputed_dept")
            if dept_name is None:
                dept_name = (job.get("department_name") or job.get("department") or "").lower()
            if dept_name and dept_name in cv_lower:
                score += 30.0

            # Title term match
            title_terms = job.get("_precomputed_title_terms")
            if title_terms is None:
                title = job.get("title", "").lower()
                title_terms = [
                    t for t in re.split(r"[\s/&()\-,]+", title)
                    if len(t) > 2 and t not in stop_words
                ]
            title_matches = [t for t in title_terms if t in cv_lower]
            score += len(title_matches) * 15.0

            # Required skills match
            req_skills = job.get("_precomputed_req_skills")
            if req_skills is None:
                req_skills = [s.lower() for s in job.get("required_skills", []) if isinstance(s, str)]
            for skill in req_skills:
                if skill in cv_lower:
                    score += 10.0

            # Preferred keywords match
            pref_keywords = job.get("_precomputed_pref_keywords")
            if pref_keywords is None:
                pref_keywords = [k.lower() for k in job.get("preferred_keywords", []) if isinstance(k, str)]
            for kw in pref_keywords:
                if kw in cv_lower:
                    score += 5.0

            # Experience suitability
            min_exp = job.get("min_experience_years")
            max_exp = job.get("max_experience_years")
            if candidate_experience is not None:
                if (min_exp is None or candidate_experience >= min_exp) and (max_exp is None or candidate_experience <= max_exp):
                    score += 10.0

            lexical_scored.append((score, job))

        # Sort descending by score to establish lexical ranks
        lexical_scored.sort(key=lambda item: item[0], reverse=True)
        lex_ranks = {}
        for rank, (score, job) in enumerate(lexical_scored, 1):
            vid = str(job.get("vacancy_id") or job.get("id"))
            lex_ranks[vid] = rank

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scored = []
        k_constant = 60.0
        for job in openings:
            vid = str(job.get("vacancy_id") or job.get("id"))
            
            l_rank = lex_ranks.get(vid)
            v_rank = vec_ranks.get(vid)
            
            fused_score = 0.0
            if l_rank:
                fused_score += 1.0 / (k_constant + l_rank)
            if v_rank:
                fused_score += 1.0 / (k_constant + v_rank)
                
            job_copy = dict(job)
            job_copy["_prefilter_score"] = fused_score
            job_copy["_rrf_details"] = {"lexical_rank": l_rank, "vector_rank": v_rank}
            rrf_scored.append((fused_score, job_copy))

        # Sort descending by fused RRF score
        rrf_scored.sort(key=lambda item: item[0], reverse=True)

        # Extract top K
        selected = [item[1] for item in rrf_scored[:limit]]

        # Logging RRF Composition
        keyword_only, vector_only, both = 0, 0, 0
        for item in selected:
            details = item.get("_rrf_details", {})
            has_l = details.get("lexical_rank") is not None
            has_v = details.get("vector_rank") is not None
            if has_l and has_v:
                both += 1
            elif has_l:
                keyword_only += 1
            elif has_v:
                vector_only += 1

        logger.info(
            f"Vacancy Pre-filter (RRF): {len(openings)} total vacancies reduced to {len(selected)} candidates (Top K={limit}). "
            f"Composition: Both={both}, Keyword-Only={keyword_only}, Vector-Only={vector_only}"
        )
        return selected
