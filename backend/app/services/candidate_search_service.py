from __future__ import annotations
from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager
from app.repositories.result import ResultRepository
from app.schemas.candidate_search import (
    CandidateSearchRequest,
    CandidateSearchResponse,
    CandidateSearchResultItem,
)
from app.services.embedding_service import EmbeddingService, get_candidate_embedding
from app.services.match_evaluators import VacancyFitEvaluator, VacancyMatchStatus
from app.services.resume_field_extractor import ResumeFieldExtractor


class CandidateSearchService:
    """
    Enterprise Semantic Candidate Search Service.
    Combines natural language vector similarity query embeddings with structured deterministic filters
    (department, experience, location, skills, education, status).
    """

    @classmethod
    def _vector_search_pg(
        cls,
        query_embedding: list[float],
        top_k: int = 200,
        search_section: str | None = None,
        section_weights: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """
        Query PostgreSQL candidate_embeddings table using cosine distance across overall or multi-vector section columns.
        Returns a dict mapping cv_key (str) to composite similarity score (0.0 to 1.0).
        """
        scores: dict[str, float] = {}
        try:
            from app.core.database import PostgresAppSession
            from app.models.pg import CandidateEmbedding

            if PostgresAppSession is not None:
                with PostgresAppSession() as session:
                    section = (search_section or "").lower().strip()
                    column_map = {
                        "profile": CandidateEmbedding.profile_embedding,
                        "skills": CandidateEmbedding.skills_embedding,
                        "experience": CandidateEmbedding.experience_embedding,
                        "projects": CandidateEmbedding.projects_embedding,
                        "domain": CandidateEmbedding.domain_embedding,
                    }

                    if section in column_map:
                        target_col = column_map[section]
                        stmt = (
                            select(
                                CandidateEmbedding.cv_key,
                                target_col.cosine_distance(query_embedding).label("section_dist"),
                                CandidateEmbedding.embedding.cosine_distance(query_embedding).label("overall_dist"),
                            )
                            .order_by("section_dist")
                            .limit(top_k)
                        )
                        results = session.execute(stmt).all()
                        for row in results:
                            cv_key = str(row.cv_key)
                            dist = row.section_dist if row.section_dist is not None else row.overall_dist
                            dist_val = float(dist) if dist is not None else 1.0
                            scores[cv_key] = round(max(0.0, 1.0 - dist_val), 4)
                    elif section in ("weighted", "all") or section_weights:
                        weights = section_weights or {
                            "skills": 0.30,
                            "experience": 0.30,
                            "profile": 0.20,
                            "projects": 0.10,
                            "domain": 0.10,
                        }
                        w_total = sum(weights.values()) or 1.0
                        norm_weights = {k: v / w_total for k, v in weights.items()}

                        stmt = select(
                            CandidateEmbedding.cv_key,
                            CandidateEmbedding.embedding.cosine_distance(query_embedding).label("overall_dist"),
                            CandidateEmbedding.profile_embedding.cosine_distance(query_embedding).label("profile_dist"),
                            CandidateEmbedding.skills_embedding.cosine_distance(query_embedding).label("skills_dist"),
                            CandidateEmbedding.experience_embedding.cosine_distance(query_embedding).label("experience_dist"),
                            CandidateEmbedding.projects_embedding.cosine_distance(query_embedding).label("projects_dist"),
                            CandidateEmbedding.domain_embedding.cosine_distance(query_embedding).label("domain_dist"),
                        ).limit(top_k)

                        results = session.execute(stmt).all()
                        for row in results:
                            cv_key = str(row.cv_key)
                            d_overall = float(row.overall_dist) if row.overall_dist is not None else 1.0
                            d_profile = float(row.profile_dist) if row.profile_dist is not None else d_overall
                            d_skills = float(row.skills_dist) if row.skills_dist is not None else d_overall
                            d_experience = float(row.experience_dist) if row.experience_dist is not None else d_overall
                            d_projects = float(row.projects_dist) if row.projects_dist is not None else d_overall
                            d_domain = float(row.domain_dist) if row.domain_dist is not None else d_overall

                            s_map = {
                                "profile": max(0.0, 1.0 - d_profile),
                                "skills": max(0.0, 1.0 - d_skills),
                                "experience": max(0.0, 1.0 - d_experience),
                                "projects": max(0.0, 1.0 - d_projects),
                                "domain": max(0.0, 1.0 - d_domain),
                            }
                            composite = sum(norm_weights.get(k, 0.0) * s_map.get(k, max(0.0, 1.0 - d_overall)) for k in norm_weights)
                            scores[cv_key] = round(composite, 4)
                    else:
                        stmt = (
                            select(
                                CandidateEmbedding.cv_key,
                                CandidateEmbedding.embedding.cosine_distance(query_embedding).label("distance"),
                            )
                            .order_by("distance")
                            .limit(top_k)
                        )
                        results = session.execute(stmt).all()
                        for row in results:
                            cv_key = str(row.cv_key)
                            dist = float(row.distance) if row.distance is not None else 1.0
                            scores[cv_key] = round(max(0.0, 1.0 - dist), 4)
        except Exception as exc:
            logger.warning(f"[CANDIDATE_SEARCH] pgvector query failed: {exc}")

        return scores

    @classmethod
    def search_candidates(cls, request: CandidateSearchRequest) -> CandidateSearchResponse:
        """
        Execute dynamic hybrid candidate search combining PGVector semantic retrieval,
        PostgreSQL FTS/trigram lexical retrieval, and structured database filtering,
        fused via Reciprocal Rank Fusion (RRF) and reranked using requirement evidence evaluation.
        """
        from app.services.candidate_search_reranker import CandidateSearchReranker
        from app.services.rank_fusion_service import RankFusionService
        from app.services.retrievers import (
            LexicalCandidateRetriever,
            StructuredCandidateRetriever,
            VectorCandidateRetriever,
        )
        from app.services.search_query_analyzer import SearchQueryAnalyzer

        explicit_filters = {
            "department": request.department,
            "min_experience": request.min_experience,
            "max_experience": request.max_experience,
            "location": request.location,
            "status": request.status,
            "include_incomplete": request.include_incomplete,
        }

        query_ctx = SearchQueryAnalyzer.analyze_query(
            query=request.query,
            filters=explicit_filters,
        )

        query_embedding: list[float] | None = None
        search_mode = "keyword"

        if query_ctx.raw_query and settings.EMBEDDING_ENABLED:
            try:
                query_embedding = EmbeddingService.generate_embedding(
                    query_ctx.semantic_text or query_ctx.raw_query,
                    model_version=settings.EMBEDDING_MODEL,
                )
                if query_embedding:
                    search_mode = "hybrid"
            except Exception as exc:
                logger.warning(f"[CANDIDATE_SEARCH] Query embedding generation failed: {exc}")

        # 1. Vector Retrieval
        vec_ranks: dict[str, int] = {}
        vec_sims: dict[str, float] = {}
        if query_embedding:
            vec_ranks, vec_sims = VectorCandidateRetriever.retrieve_candidates(
                query_embedding=query_embedding,
                top_k=200,
                section_type=request.search_section,
                model_version=settings.EMBEDDING_MODEL,
            )

        # 2. Lexical FTS Retrieval
        lex_ranks: dict[str, int] = {}
        lex_scores: dict[str, float] = {}
        if query_ctx.raw_query:
            lex_ranks, lex_scores = LexicalCandidateRetriever.retrieve_candidates(
                query_text=query_ctx.raw_query,
                top_k=200,
            )

        # 3. Structured Candidate Retrieval
        struct_ranks: dict[str, int] = {}
        if any(v is not None for v in query_ctx.filters.values()):
            struct_ranks = StructuredCandidateRetriever.retrieve_candidates(
                filters=query_ctx.filters,
                top_k=200,
            )

        # 4. Domain-Agnostic Reciprocal Rank Fusion (RRF)
        fused_items = RankFusionService.fuse_rankings(
            vector_ranks=vec_ranks,
            lexical_ranks=lex_ranks,
            structured_ranks=struct_ranks,
            vector_similarities=vec_sims,
            lexical_scores=lex_scores,
            k_constant=getattr(settings, "RRF_K_CONSTANT", 60.0),
        )

        # Fallback to direct file loading if DB retrievers returned empty set
        if not fused_items:
            results = ResultRepository.list_all_results(include_incomplete=request.include_incomplete)
            for rank_idx, r in enumerate(results[: request.limit], start=1):
                if r and isinstance(r, dict):
                    k = str(r.get("id") or r.get("filename") or "").removesuffix(".json")
                    if k:
                        vec_ranks[k] = rank_idx
            fused_items = RankFusionService.fuse_rankings(vector_ranks=vec_ranks)

        # 5. Candidate Search Reranker & Hiring Evaluation Separation
        scoring_parameters = RuleConfigManager.get_scoring_parameters()
        reranked_records = CandidateSearchReranker.rerank_retrieved_candidates(
            rank_items=fused_items,
            high_threshold=scoring_parameters.match_high_threshold,
            potential_threshold=scoring_parameters.match_medium_threshold,
            limit=request.limit,
        )

        items: list[CandidateSearchResultItem] = []
        for r in reranked_records:
            cv_key = str(r.get("id") or r.get("filename") or "").removesuffix(".json")
            is_complete = ResultRepository.is_completed_result(r)
            if not request.include_incomplete and not is_complete:
                continue

            resume_json = r.get("resume_json") or {}
            contact_info = resume_json.get("contact_info") or {}
            match_analysis = r.get("match_analysis") or {}
            best_match = r.get("best_match") or {}

            extracted_name = (
                r.get("full_name")
                or r.get("candidate_name")
                or contact_info.get("name")
                or contact_info.get("full_name")
                or match_analysis.get("full_name")
            )
            email = r.get("email") or contact_info.get("email")
            phone = r.get("phone") or contact_info.get("phone")

            raw_fc = r.get("field_confidence") or contact_info.get("field_confidence") or {}
            raw_fct = r.get("field_confidence_tiers") or contact_info.get("field_confidence_tiers") or {}

            location_val = r.get("location") or contact_info.get("location")
            job_title_val = r.get("job_title") or contact_info.get("job_title") or best_match.get("job_title")
            company_val = (
                r.get("company_name")
                or r.get("company")
                or contact_info.get("company_name")
                or contact_info.get("company")
            )

            name_tier = (
                r.get("name_confidence_tier")
                or raw_fct.get("name")
                or contact_info.get("name_confidence_level")
                or RuleConfigManager.get_confidence_tier("name", r.get("name_confidence") or raw_fc.get("name"))
            )
            loc_tier = (
                r.get("location_confidence_tier")
                or raw_fct.get("location")
                or RuleConfigManager.get_confidence_tier("location", r.get("location_confidence") or raw_fc.get("location"))
            )
            title_tier = (
                r.get("job_title_confidence_tier")
                or raw_fct.get("job_title")
                or RuleConfigManager.get_confidence_tier(
                    "job_title",
                    r.get("job_title_confidence") or raw_fc.get("job_title"),
                )
            )
            comp_tier = (
                r.get("company_name_confidence_tier")
                or raw_fct.get("company_name")
                or RuleConfigManager.get_confidence_tier(
                    "company_name",
                    r.get("company_name_confidence") or raw_fc.get("company_name"),
                )
            )

            fct = {
                "name": name_tier if extracted_name and extracted_name.lower() != "unknown candidate" else "LOW",
                "location": loc_tier if location_val else "LOW",
                "job_title": title_tier if job_title_val else "LOW",
                "company_name": comp_tier if company_val else "LOW",
            }

            cand_exp = r.get("experience_years")
            if cand_exp is None:
                cand_exp = r.get("total_experience_years")

            items.append(
                CandidateSearchResultItem(
                    id=r.get("id") or cv_key,
                    result_generation_id=r.get("result_generation_id"),
                    filename=r.get("filename") or f"{cv_key}.pdf",
                    full_name=extracted_name if (extracted_name and extracted_name.lower() != "unknown candidate") else None,
                    email=email if email else None,
                    phone=phone if phone else None,
                    location=location_val if location_val else None,
                    job_title=job_title_val if job_title_val else None,
                    company_name=company_val if company_val else None,
                    name_confidence_tier=fct["name"],
                    location_confidence_tier=fct["location"],
                    job_title_confidence_tier=fct["job_title"],
                    company_name_confidence_tier=fct["company_name"],
                    field_confidence=raw_fc if raw_fc else None,
                    field_confidence_tiers=fct,
                    parsed_at=r.get("parsed_at") or r.get("created_at"),
                    page_count=r.get("page_count", 1),
                    is_scanned=r.get("is_scanned", False),
                    ocr_applied=r.get("ocr_applied", False),
                    is_complete=is_complete,
                    processing_stage=str(r.get("stage") or r.get("processing_stage") or r.get("status") or "") if not is_complete else "COMPLETED",
                    primary_department=match_analysis.get("primary_department"),
                    experience_years=cand_exp,
                    gross_display=r.get("gross_display") or (r.get("experience_summary") or {}).get("gross_display"),
                    experience_state=r.get("experience_state") or (r.get("experience_summary") or {}).get("experience_state"),
                    similarity_score=vec_sims.get(cv_key) or r.get("_final_score"),
                    search_mode=search_mode,
                    best_match=best_match,
                )
            )

        if not request.query:
            def _parse_item_ts(val: Any) -> float:
                if not val:
                    return 0.0
                if isinstance(val, (int, float)):
                    return float(val)
                if isinstance(val, str):
                    v = val.strip()
                    if not v:
                        return 0.0
                    try:
                        from datetime import datetime
                        return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
                    except Exception:
                        try:
                            return float(v)
                        except Exception:
                            return 0.0
                return 0.0

            items.sort(key=lambda item: _parse_item_ts(item.parsed_at), reverse=True)

        return CandidateSearchResponse(
            total_found=len(items),
            search_mode=search_mode,
            query=request.query,
            candidates=items,
        )
