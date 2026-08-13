from __future__ import annotations
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
from app.services.job_taxonomy import TaxonomyClassifier
from app.services.quality_metrics import QualityMetrics
class InsufficientEvidenceError(Exception):
    """Raised when candidate CV lacks sufficient evidence to determine a safe matching domain."""
    pass


class AnalysisUnavailableError(Exception):
    """Raised when required taxonomy/configuration is unavailable to perform matching."""
    pass


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
    taxonomy_confidence: float = 1.0
    taxonomy_match_status: str = "DB_MATCH"
    taxonomy_match_source: str | None = None
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
                    cv_embedding = EmbeddingService.generate_embedding(cv_text, settings.EMBEDDING_MODEL)
                except (RuntimeError, ValueError, AttributeError, KeyError) as e:
                    logger.warning(f"[PREFILTER] CV embedding generation failed: {e}")
                    cv_embedding = None

        if analysis_context is not None:
            cand_domain = analysis_context.cand_tax_domain
            cand_families = list(analysis_context.cand_families)
            taxonomy_confidence = analysis_context.taxonomy_confidence
            taxonomy_match_status = analysis_context.taxonomy_match_status
            taxonomy_match_source = analysis_context.taxonomy_match_source
            candidate_experience = analysis_context.candidate_experience
        else:
            cand_domain, cand_families, taxonomy_confidence, taxonomy_status, taxonomy_match_source = (
                TaxonomyClassifier.classify_candidate_with_confidence(cv_text, resume_json=resume_json)
            )
            taxonomy_match_status = taxonomy_status.value

        return cls(
            cv_text=cv_text,
            cv_lower=cv_lower,
            cv_tokens=cv_tokens,
            candidate_experience=candidate_experience,
            cv_embedding=cv_embedding,
            cand_domain=cand_domain,
            cand_families=cand_families,
            taxonomy_confidence=taxonomy_confidence,
            taxonomy_match_status=taxonomy_match_status,
            taxonomy_match_source=taxonomy_match_source,
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

            from app.core.database import PostgresAppSession
            from app.models.pg import VacancyEmbedding

            if PostgresAppSession is not None:
                embedding_list = list(embedding_tuple)
                with PostgresAppSession() as session:
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

        rrf_scored.sort(key=lambda item: (-item[0], item[2].job_id))
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
        taxonomy_rules = RuleConfigManager.get_taxonomy_rules()
        
        # 1. Missing Taxonomy
        if not taxonomy_rules.candidate_rules or not taxonomy_rules.canonical_domains:
            raise AnalysisUnavailableError("Taxonomy/configuration is unavailable")

        default_family = taxonomy_rules.default_family
        candidate_taxonomy_resolved = bool(
            cand_ctx.cand_domain not in (None, "", "Unknown", "Not Configured")
            and cand_ctx.cand_families
            and cand_ctx.cand_families not in ([default_family], ["Unknown"], ["Not Configured"])
        )
        candidate_taxonomy_confident = candidate_taxonomy_resolved and cand_ctx.taxonomy_confidence >= taxonomy_rules.semantic_match_threshold

        top_n = getattr(settings, "SEMANTIC_RETRIEVAL_TOP_N", 50)
        vector_results_tuple: tuple[tuple[str, int, float], ...] = ()
        if cand_ctx.cv_embedding and settings.EMBEDDING_ENABLED:
            vector_results_tuple = PgVectorQueryCache.query_pgvector_cached(tuple(cand_ctx.cv_embedding), top_limit=max(top_n, 200))
        semantic_top_ids = {vid for vid, _rank, _dist in vector_results_tuple[:top_n]}

        if candidate_taxonomy_confident:
            # 2. High-confidence candidate taxonomy can safely constrain the search space.
            stage0_jobs = [
                j for j in job_contexts 
                if j.vac_tax_domain in ("Unknown", "Not Configured") 
                or j.vac_family in ("Unknown", "Not Configured") 
                or TaxonomyClassifier.are_families_compatible(cand_ctx.cand_families, j.vac_family) 
                or j.vac_tax_domain == cand_ctx.cand_domain
            ]
        else:
            # 3. Low-confidence or unresolved taxonomy remains a ranking signal, never a permanent exclusion.
            stage0_jobs = job_contexts

        stage0_ids = {job.job_id for job in stage0_jobs}
        for job in job_contexts:
            if job.job_id in stage0_ids:
                continue
            semantic_contradiction = job.job_id in semantic_top_ids
            logger.info(
                f"[PREFILTER_EXCLUSION] vacancy_id={job.job_id} stage=0 reason=HIGH_CONFIDENCE_TAXONOMY_MISMATCH "
                f"candidate_domain='{cand_ctx.cand_domain}' candidate_families={cand_ctx.cand_families} "
                f"taxonomy_confidence={cand_ctx.taxonomy_confidence:.4f} taxonomy_source='{cand_ctx.taxonomy_match_source or 'unknown'}' "
                f"vacancy_domain='{job.vac_tax_domain}' vacancy_family='{job.vac_family}' "
                f"semantic_top_n_contradiction={semantic_contradiction}"
            )

        t_stage0_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        logger.info(
            f"[PREFILTER_STAGE_0] Candidate Domain='{cand_ctx.cand_domain}', Families={cand_ctx.cand_families}. "
            f"Filtered {len(job_contexts)} initial openings down to {len(stage0_jobs)} retrieval candidates "
            f"(candidate_taxonomy_resolved={candidate_taxonomy_resolved}, candidate_taxonomy_confident={candidate_taxonomy_confident}, "
            f"taxonomy_confidence={cand_ctx.taxonomy_confidence:.4f}) in {t_stage0_ms} ms."
        )

        # Adaptive Retrieval Guard: Skip Stage 1 & 2 if Stage 0 count <= limit
        if len(stage0_jobs) <= limit:
            logger.info(f"[PREFILTER_ADAPTIVE] Stage 0 compatible openings ({len(stage0_jobs)}) <= limit ({limit}). Skipping Stage 1 & 2 retrieval.")
            res_jobs = []
            stage0_jobs = sorted(stage0_jobs, key=lambda item: item.job_id)
            for rank, j in enumerate(stage0_jobs, start=1):
                job_dict = dict(j.raw_job) if isinstance(j.raw_job, dict) and j.raw_job else dict(j.__dict__)
                job_dict["_prefilter_score"] = 100.0
                job_dict["_rrf_details"] = {
                    "rrf_score": 1.0,
                    "prefilter_rank": rank,
                    "stage0_compatible": candidate_taxonomy_confident,
                    "retrieval_path": "taxonomy" if candidate_taxonomy_confident else "confidence_fallback",
                    "taxonomy_confidence": cand_ctx.taxonomy_confidence,
                }
                j.raw_job = job_dict
                res_jobs.append(job_dict)
            QualityMetrics.record(
                "retrieval",
                openings=len(job_contexts),
                selected=len(res_jobs),
                stage0_exclusions=len(job_contexts) - len(stage0_jobs),
                vector_coverage=0,
            )
            return stage0_jobs if return_contexts else res_jobs

        # STAGE 1: Semantic Vector Retrieval (Single pgvector Query Reuse)
        t1 = time.perf_counter()
        stage1_jobs = stage0_jobs
        semantic_candidate_count = sum(job.job_id in semantic_top_ids for job in stage0_jobs)

        t_stage1_ms = round((time.perf_counter() - t1) * 1000.0, 2)
        logger.info(
            f"[PREFILTER_STAGE_1] Semantic Retrieval ranked {semantic_candidate_count} of {len(stage0_jobs)} Stage 0 openings; "
            f"all Stage 0 openings remain eligible for lexical+vector fusion in {t_stage1_ms} ms."
        )

        # STAGE 2: Deterministic VacancyPreFilter (Fast Token-Set Lexical + RRF fusion)
        t2 = time.perf_counter()

        # Extract precompiled vector ranks dict from the single query result
        vec_ranks = {vid: rank for vid, rank, _dist in vector_results_tuple[:top_n]} if vector_results_tuple else {}
        vec_distances = {vid: dist for vid, _rank, dist in vector_results_tuple[:top_n]} if vector_results_tuple else {}

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
        lexical_scored.sort(key=lambda item: (-item[0], item[1].job_id))
        lex_ranks = {job.job_id: rank for rank, (score, job) in enumerate(lexical_scored, 1) if score > 0.0}

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
            rrf_details["prefilter_rank"] = len(selected_contexts) + 1
            rrf_details["rrf_score"] = fused_score
            rrf_details["vector_distance"] = vec_distances.get(job.job_id)
            rrf_details["stage0_compatible"] = candidate_taxonomy_confident and (
                TaxonomyClassifier.are_families_compatible(cand_ctx.cand_families, job.vac_family)
                or job.vac_tax_domain == cand_ctx.cand_domain
            )
            rrf_details["taxonomy_confidence"] = cand_ctx.taxonomy_confidence
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
        selected_ids = {job.job_id for job in selected_contexts}
        for job in stage0_jobs:
            if job.job_id in selected_ids:
                continue
            logger.info(
                f"[PREFILTER_EXCLUSION] vacancy_id={job.job_id} stage=2 reason=RRF_TOP_K "
                f"taxonomy_confidence={cand_ctx.taxonomy_confidence:.4f} lexical_rank={lex_ranks.get(job.job_id)} "
                f"vector_rank={vec_ranks.get(job.job_id)} semantic_top_n={job.job_id in semantic_top_ids}"
            )
        QualityMetrics.record(
            "retrieval",
            openings=len(job_contexts),
            selected=len(selected_results),
            stage0_exclusions=len(job_contexts) - len(stage0_jobs),
            vector_coverage=len(vec_ranks),
            lexical_and_vector=both,
            lexical_only=keyword_only,
            vector_only=vector_only,
        )

        if return_contexts:
            return selected_contexts
        return selected_results
