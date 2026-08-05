import functools
import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.core.rule_config_manager import PrefilterRules, RuleConfigManager
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.services.dynamic_scoring_prefilter_service import (
    DynamicScoringAndPrefilterService,
)
from app.services.embedding_service import EmbeddingService, get_candidate_embedding
from app.services.job_taxonomy import JobTaxonomy, TaxonomyClassifier


@dataclass
class CandidateSearchContext:
    """Encapsulates precomputed candidate state for batch vacancy prefiltering."""

    cv_text: str
    cv_lower: str
    cv_tokens: set[str]
    candidate_experience: float | None = None
    cv_embedding: list[float] | None = None
    cand_domain: str = ""
    cand_families: list[str] = field(default_factory=list)
    resume_json: dict[str, Any] | None = None

    @classmethod
    def create(
        cls,
        cv_text: str,
        *,
        candidate_experience: float | None = None,
        cv_embedding: list[float] | None = None,
        resume_json: dict[str, Any] | None = None,
        analysis_context: CandidateAnalysisContext | None = None,
    ) -> "CandidateSearchContext":
        cv_lower = cv_text.lower()
        cv_tokens = set(re.findall(r"\w+", cv_lower))

        # Check existing cached candidate embedding first before generating
        if cv_embedding is None and settings.EMBEDDING_ENABLED:
            cv_hash = hashlib.sha256(cv_text.encode("utf-8")).hexdigest()
            cv_embedding = get_candidate_embedding(cv_hash)
            if cv_embedding is None:
                try:
                    cv_embedding = EmbeddingService.generate_embedding(cv_text[:8000], settings.EMBEDDING_MODEL)
                except (RuntimeError, ValueError, AttributeError, KeyError) as e:
                    logger.warning(f"[PREFILTER] CV embedding generation failed: {e}")
                    cv_embedding = None

        if analysis_context is not None:
            cand_domain = analysis_context.cand_tax_domain
            cand_families = list(analysis_context.cand_families)
            candidate_experience = analysis_context.candidate_experience
        else:
            cand_domain, cand_families = TaxonomyClassifier.classify_candidate(cv_text, resume_json=resume_json)

        return cls(
            cv_text=cv_text,
            cv_lower=cv_lower,
            cv_tokens=cv_tokens,
            candidate_experience=candidate_experience,
            cv_embedding=cv_embedding,
            cand_domain=cand_domain,
            cand_families=cand_families,
            resume_json=resume_json,
        )


class PgVectorQueryCache:
    """Caches pgvector similarity queries to ensure PostgreSQL is queried ONLY ONCE per embedding."""

    @staticmethod
    @functools.lru_cache(maxsize=128)
    def query_pgvector_cached(embedding_tuple: tuple[float, ...], top_limit: int = 200) -> tuple[tuple[str, int, float], ...]:
        """
        Queries pgvector ONCE for candidate embedding, returning tuple of (vacancy_id, rank, distance).
        Thread-safe under CPython GIL atomic LRU cache operations.
        """
        results_list: list[tuple[str, int, float]] = []
        try:
            from sqlalchemy import select

            from app.core.database import pg_SessionLocal
            from app.models.pg import VacancyEmbedding

            if pg_SessionLocal is not None:
                embedding_list = list(embedding_tuple)
                with pg_SessionLocal() as session:
                    dist_col = VacancyEmbedding.embedding.cosine_distance(embedding_list)
                    stmt = select(VacancyEmbedding.vacancy_id, dist_col).order_by(dist_col).limit(top_limit)
                    rows = session.execute(stmt).all()
                    for rank, (vid, dist) in enumerate(rows, 1):
                        results_list.append((str(vid), rank, float(dist or 0.0)))
        except Exception as e:
            logger.warning(f"[PREFILTER] pgvector single similarity query failed: {e}")

        return tuple(results_list)


class ReciprocalRankFusionService:
    """Dedicated helper service for Reciprocal Rank Fusion (RRF) scoring."""

    @staticmethod
    def fuse_ranks(
        stage1_jobs: list[JobEvaluationContext],
        lex_ranks: dict[str, int],
        vec_ranks: dict[str, int],
        k_constant: float = 60.0,
    ) -> list[tuple[float, dict[str, Any], JobEvaluationContext]]:
        """
        Fuses lexical ranks and vector ranks using RRF formula score = 1/(k + r_lex) + 1/(k + r_vec).
        Returns list of (fused_score, rrf_details_dict, job_context) sorted descending.
        """
        rrf_scored = []
        for job in stage1_jobs:
            vid = job.job_id
            l_rank = lex_ranks.get(vid)
            v_rank = vec_ranks.get(vid)

            fused_score = 0.0
            if l_rank:
                fused_score += 1.0 / (k_constant + l_rank)
            if v_rank:
                fused_score += 1.0 / (k_constant + v_rank)

            rrf_details = {"lexical_rank": l_rank, "vector_rank": v_rank}
            rrf_scored.append((fused_score, rrf_details, job))

        rrf_scored.sort(key=lambda item: item[0], reverse=True)
        return rrf_scored


class VacancyPreFilter:
    """
    Three-stage Vacancy Pre-Filter:
    - Stage 0 (Taxonomy Search Space Filtering): Classifies candidate CV into primary domain & job families and prunes cross-domain search space.
    - Stage 1 (Semantic Retrieval): First-stage vector search narrows down active vacancies to Top-N semantic candidates.
    - Stage 2 (Deterministic Pre-filtering): Evaluates lexical scoring, title matching, required skills, and RRF fusion.
    The Deterministic Scoring Engine remains the final authority for ranking.
    """

    @classmethod
    def semantic_vector_search(cls, candidate_embedding: list[float], top_n: int = 50) -> list[str]:
        """
        Performs vector similarity search against active vacancy embeddings.
        Uses PgVectorQueryCache to ensure pgvector is queried ONLY ONCE.
        Returns a list of vacancy_id strings ordered by proximity.
        """
        if not candidate_embedding:
            return []
        cached_results = PgVectorQueryCache.query_pgvector_cached(tuple(candidate_embedding), top_limit=max(top_n, 200))
        return [vid for vid, rank, dist in cached_results[:top_n]]

    @classmethod
    def vector_prefilter(cls, candidate_embedding: list[float], top_k: int = 200) -> dict[str, int]:
        """
        Executes a pgvector cosine distance query against PostgreSQL.
        Uses PgVectorQueryCache to ensure pgvector is queried ONLY ONCE.
        Returns a dict mapping vacancy_id (str) to its vector rank (1-indexed).
        """
        if not candidate_embedding:
            return {}
        cached_results = PgVectorQueryCache.query_pgvector_cached(tuple(candidate_embedding), top_limit=max(top_k, 200))
        return {vid: rank for vid, rank, dist in cached_results[:top_k]}

    @classmethod
    def filter_vacancies(
        cls,
        cv_text: str,
        openings: list[dict[str, Any]] | list[JobEvaluationContext],
        candidate_experience: float | None = None,
        top_k: int | None = None,
        cv_embedding: list[float] | None = None,
        resume_json: dict[str, Any] | None = None,
        analysis_context: CandidateAnalysisContext | None = None,
        return_contexts: bool = False,
    ) -> list[dict[str, Any]] | list[JobEvaluationContext]:
        t_total_start = time.perf_counter()
        if not openings:
            return []

        limit = top_k or settings.PREFILTER_TOP_K

        # Convert openings to JobEvaluationContexts once if needed
        job_contexts: list[JobEvaluationContext] = [j if isinstance(j, JobEvaluationContext) else JobEvaluationContext.create(j) for j in openings]

        # Fast exit if total openings <= limit
        if len(job_contexts) <= limit:
            if return_contexts:
                return job_contexts
            return [j.raw_job if isinstance(j.raw_job, dict) and j.raw_job else j.__dict__ for j in job_contexts]

        # Load prefilter configuration rules ONCE (dynamic MSSQL stop_words & weights)
        prefilter_rules: PrefilterRules = DynamicScoringAndPrefilterService.get_prefilter_rules()

        # Batch candidate preparation
        cand_ctx = CandidateSearchContext.create(
            cv_text=cv_text,
            candidate_experience=candidate_experience,
            cv_embedding=cv_embedding,
            resume_json=resume_json,
            analysis_context=analysis_context,
        )

        # STAGE 0: Job Taxonomy Search Space Filtering
        t0 = time.perf_counter()
        stage0_jobs = job_contexts
        if cand_ctx.cand_families and cand_ctx.cand_families != [RuleConfigManager.get_taxonomy_rules().default_family]:
            compatible_jobs = [j for j in job_contexts if TaxonomyClassifier.are_families_compatible(cand_ctx.cand_families, j.vac_family) or j.vac_tax_domain == cand_ctx.cand_domain]
            if compatible_jobs:
                stage0_jobs = compatible_jobs

        t_stage0_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        logger.info(
            f"[PREFILTER_STAGE_0] Candidate Domain='{cand_ctx.cand_domain}', Families={cand_ctx.cand_families}. "
            f"Filtered {len(job_contexts)} initial openings down to {len(stage0_jobs)} taxonomy-compatible vacancies in {t_stage0_ms} ms."
        )

        # Adaptive Retrieval Guard: Skip Stage 1 & 2 if Stage 0 count <= limit
        if len(stage0_jobs) <= limit:
            logger.info(f"[PREFILTER_ADAPTIVE] Stage 0 compatible openings ({len(stage0_jobs)}) <= limit ({limit}). Skipping Stage 1 & 2 retrieval.")
            res_jobs = []
            for j in stage0_jobs:
                job_dict = dict(j.raw_job) if isinstance(j.raw_job, dict) and j.raw_job else dict(j.__dict__)
                job_dict["_prefilter_score"] = 100.0
                job_dict["_rrf_details"] = {"rrf_score": 1.0, "stage0_compatible": True}
                j.raw_job = job_dict
                res_jobs.append(job_dict)
            return stage0_jobs if return_contexts else res_jobs

        # STAGE 1: Semantic Vector Retrieval (Single pgvector Query Reuse)
        t1 = time.perf_counter()
        stage1_jobs = stage0_jobs
        vector_results_tuple: tuple[tuple[str, int, float], ...] = ()

        if cand_ctx.cv_embedding and settings.EMBEDDING_ENABLED:
            top_n = getattr(settings, "SEMANTIC_RETRIEVAL_TOP_N", 50)
            vector_results_tuple = PgVectorQueryCache.query_pgvector_cached(tuple(cand_ctx.cv_embedding), top_limit=max(top_n, 200))

            if vector_results_tuple:
                top_n_vids = {vid for vid, rank, dist in vector_results_tuple[:top_n]}
                semantic_candidates = [j for j in stage0_jobs if j.job_id in top_n_vids]
                if semantic_candidates:
                    stage1_jobs = semantic_candidates

        t_stage1_ms = round((time.perf_counter() - t1) * 1000.0, 2)
        logger.info(f"[PREFILTER_STAGE_1] Semantic Retrieval selected {len(stage1_jobs)} candidate vacancies out of {len(stage0_jobs)} Stage 0 openings in {t_stage1_ms} ms.")

        # STAGE 2: Deterministic VacancyPreFilter (Fast Token-Set Lexical + RRF fusion)
        t2 = time.perf_counter()

        # Extract precompiled vector ranks dict from the single query result
        vec_ranks = {vid: rank for vid, rank, dist in vector_results_tuple} if vector_results_tuple else {}

        # Compute Lexical Scores using Fast Token Set Intersections
        lexical_scored: list[tuple[float, JobEvaluationContext]] = []
        for job in stage1_jobs:
            score = 0.0

            # 1. Department term match (set intersection with cand_ctx.cv_tokens)
            if job.dept_terms:
                if any(t in cand_ctx.cv_tokens for t in job.dept_terms):
                    score += prefilter_rules.lexical_weights.department_match
            elif job.department_lower and job.department_lower in cand_ctx.cv_lower:
                score += prefilter_rules.lexical_weights.department_match

            # 2. Title term match (fast set intersection)
            if job.title_words:
                title_matches = cand_ctx.cv_tokens.intersection(job.title_words)
                score += len(title_matches) * prefilter_rules.lexical_weights.title_term_match

            # 3. Required skills match (fast token set intersection for single-word, substring for multi-word)
            for skill in job.required_skills:
                skill_lower = skill.lower().strip()
                if not skill_lower:
                    continue
                if " " in skill_lower or "-" in skill_lower or "/" in skill_lower:
                    if skill_lower in cand_ctx.cv_lower:
                        score += prefilter_rules.lexical_weights.required_skill_match
                elif skill_lower in cand_ctx.cv_tokens:
                    score += prefilter_rules.lexical_weights.required_skill_match

            # 4. Preferred keywords match
            for kw in job.preferred_keywords:
                kw_lower = kw.lower().strip()
                if not kw_lower:
                    continue
                if " " in kw_lower or "-" in kw_lower or "/" in kw_lower:
                    if kw_lower in cand_ctx.cv_lower:
                        score += prefilter_rules.lexical_weights.preferred_keyword_match
                elif kw_lower in cand_ctx.cv_tokens:
                    score += prefilter_rules.lexical_weights.preferred_keyword_match

            # 5. Experience suitability
            if cand_ctx.candidate_experience is not None:
                min_e = job.min_experience_years
                max_e = job.max_experience_years
                if (min_e is None or cand_ctx.candidate_experience >= min_e) and (max_e is None or cand_ctx.candidate_experience <= max_e):
                    score += prefilter_rules.lexical_weights.experience_suitability

            lexical_scored.append((score, job))

        # Sort descending to establish 1-indexed lexical ranks
        lexical_scored.sort(key=lambda item: item[0], reverse=True)
        lex_ranks = {job.job_id: rank for rank, (s, job) in enumerate(lexical_scored, 1)}

        t_lexical_ms = round((time.perf_counter() - t2) * 1000.0, 2)

        # 3. Reciprocal Rank Fusion (RRF) via ReciprocalRankFusionService
        t3 = time.perf_counter()
        rrf_scored = ReciprocalRankFusionService.fuse_ranks(
            stage1_jobs=stage1_jobs,
            lex_ranks=lex_ranks,
            vec_ranks=vec_ranks,
            k_constant=prefilter_rules.rrf_k_constant,
        )
        t_rrf_ms = round((time.perf_counter() - t3) * 1000.0, 2)

        # Extract Top-K Selected Jobs & Attach Metadata without shallow dict copies
        selected_results: list[dict[str, Any]] = []
        selected_contexts: list[JobEvaluationContext] = []
        keyword_only, vector_only, both = 0, 0, 0

        for fused_score, rrf_details, job in rrf_scored[:limit]:
            has_l = rrf_details.get("lexical_rank") is not None
            has_v = rrf_details.get("vector_rank") is not None
            if has_l and has_v:
                both += 1
            elif has_l:
                keyword_only += 1
            elif has_v:
                vector_only += 1

            # Prepare return dictionary efficiently
            job_dict = job.raw_job if isinstance(job.raw_job, dict) and job.raw_job else job.__dict__.copy()
            job_dict["_prefilter_score"] = fused_score
            job_dict["_rrf_details"] = rrf_details
            job.raw_job = job_dict
            selected_results.append(job_dict)
            selected_contexts.append(job)

        total_ms = round((time.perf_counter() - t_total_start) * 1000.0, 2)

        logger.info(
            f"[PREFILTER_COMPLETED] {len(job_contexts)} initial -> {len(stage0_jobs)} Stage 0 -> "
            f"{len(stage1_jobs)} Stage 1 -> {len(selected_results)} final selected (Top K={limit}) in {total_ms} ms. "
            f"Composition: Both={both}, Keyword-Only={keyword_only}, Vector-Only={vector_only} | "
            f"Timings: Stage0={t_stage0_ms}ms, Stage1={t_stage1_ms}ms, Lexical={t_lexical_ms}ms, RRF={t_rrf_ms}ms"
        )

        if return_contexts:
            return selected_contexts
        return selected_results
