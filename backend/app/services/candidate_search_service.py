import math
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.repositories.result import ResultRepository
from app.schemas.candidate_search import (
    CandidateSearchRequest,
    CandidateSearchResponse,
    CandidateSearchResultItem,
)
from app.core.rule_config_manager import RuleConfigManager
from app.services.embedding_service import EmbeddingService, get_candidate_embedding


class CandidateSearchService:
    """
    Enterprise Semantic Candidate Search Service.
    Combines natural language vector similarity query embeddings with structured deterministic filters
    (department, experience, location, skills, education, status).
    """

    @classmethod
    def _vector_search_pg(cls, query_embedding: list[float], top_k: int = 200) -> dict[str, float]:
        """
        Query PostgreSQL candidate_embeddings table using cosine distance.
        Returns a dict mapping cv_key (str) to similarity score (0.0 to 1.0).
        """
        scores: dict[str, float] = {}
        try:
            from app.core.database import pg_SessionLocal
            from app.models.pg import CandidateEmbedding

            if pg_SessionLocal is not None:
                with pg_SessionLocal() as session:
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
                        sim = round(max(0.0, 1.0 - dist), 4)
                        scores[cv_key] = sim
        except Exception as exc:
            logger.warning(f"[CANDIDATE_SEARCH] pgvector query failed: {exc}")

        return scores

    @classmethod
    def search_candidates(cls, request: CandidateSearchRequest) -> CandidateSearchResponse:
        """
        Execute semantic candidate search and apply deterministic filtering.
        """
        results = ResultRepository.list_all_results()

        search_mode = "keyword"
        query_embedding: list[float] | None = None
        vector_scores: dict[str, float] = {}

        if request.query and request.query.strip() and settings.EMBEDDING_ENABLED:
            query_str = request.query.strip()
            try:
                query_embedding = EmbeddingService.generate_embedding(
                    query_str, model_version=settings.EMBEDDING_MODEL
                )
                if query_embedding:
                    search_mode = "semantic"
                    vector_scores = cls._vector_search_pg(query_embedding, top_k=200)
            except Exception as exc:
                logger.warning(f"[CANDIDATE_SEARCH] Query embedding generation failed: {exc}")

        items: list[CandidateSearchResultItem] = []

        for r in results:
            if not r or not isinstance(r, dict):
                continue

            cv_key = str(r.get("id") or r.get("filename") or "")
            if cv_key.endswith(".json"):
                cv_key = cv_key[:-5]

            raw_match = r.get("match_analysis")
            match_analysis = raw_match if isinstance(raw_match, dict) else {}
            best_match = match_analysis.get("best_match") or {}

            resume_json = r.get("resume_json") or {}
            contact_info = resume_json.get("contact_info") or {}
            extracted_name = (
                r.get("full_name")
                or r.get("candidate_name")
                or contact_info.get("name")
                or contact_info.get("full_name")
                or match_analysis.get("full_name")
            )
            email = r.get("email") or contact_info.get("email")
            phone = r.get("phone") or contact_info.get("phone")

            markdown_text = str(r.get("markdown") or r.get("text") or "")
            text_lower = markdown_text.lower()

            # Compute similarity score
            sim_score: float | None = None
            if search_mode == "semantic" and query_embedding:
                if cv_key in vector_scores:
                    sim_score = vector_scores[cv_key]
                else:
                    # Fallback lookup from cache/DB or on-the-fly similarity
                    cand_emb = get_candidate_embedding(cv_key)
                    if cand_emb is not None:
                        sim_score = round(EmbeddingService.cosine_similarity(query_embedding, cand_emb), 4)
                    elif markdown_text:
                        # Generate candidate embedding dynamically
                        gen_emb = EmbeddingService.generate_embedding(
                            markdown_text[:3000], identifier=cv_key
                        )
                        if gen_emb:
                            sim_score = round(EmbeddingService.cosine_similarity(query_embedding, gen_emb), 4)

            # Keyword Search Filter (if search_mode == "keyword" and query is provided)
            if search_mode == "keyword" and request.query and request.query.strip():
                q_lower = request.query.strip().lower()
                fname = str(r.get("filename") or "").lower()
                if q_lower not in fname and q_lower not in cv_key.lower() and q_lower not in text_lower:
                    continue

            # Minimum Similarity Filter
            if request.min_similarity is not None and sim_score is not None:
                if sim_score < request.min_similarity:
                    continue

            # Department Filter
            if request.department:
                dept_req = request.department.strip().lower()
                cand_dept = str(
                    match_analysis.get("primary_department")
                    or best_match.get("department")
                    or best_match.get("department_name")
                    or ""
                ).lower()
                if dept_req not in cand_dept and cand_dept not in dept_req:
                    continue

            if request.department_id is not None:
                cand_dept_id = best_match.get("department_id")
                if cand_dept_id is not None and int(cand_dept_id) != int(request.department_id):
                    continue

            # Experience Range Filter
            quality_metrics = r.get("quality_metrics") or {}
            cand_exp = quality_metrics.get("experience_years")
            if cand_exp is None:
                cand_exp = r.get("candidate_experience")

            if request.min_experience is not None:
                if cand_exp is not None and cand_exp < request.min_experience:
                    continue

            if request.max_experience is not None:
                if cand_exp is not None and cand_exp > request.max_experience:
                    continue

            # Location Filter
            if request.location:
                loc_req = request.location.strip().lower()
                location_text = str(r.get("location") or contact_info.get("location") or "").lower()
                if loc_req not in location_text and loc_req not in text_lower:
                    continue

            # Required Skills Filter
            if request.skills:
                cand_skills = [
                    s.lower()
                    for s in (
                        best_match.get("matched_skills", [])
                        + resume_json.get("skills", [])
                    )
                    if isinstance(s, str)
                ]
                missing_any_skill = False
                for req_s in request.skills:
                    s_lower = req_s.strip().lower()
                    if not any(s_lower in cs for cs in cand_skills) and s_lower not in text_lower:
                        missing_any_skill = True
                        break
                if missing_any_skill:
                    continue

            # Education Filter
            if request.education:
                edu_req = request.education.strip().lower()
                edu_text = str(resume_json.get("education") or "").lower()
                if edu_req not in edu_text and edu_req not in text_lower:
                    continue

            # Status Filter
            if request.status:
                cand_status = str(r.get("status") or "complete").lower()
                if request.status.strip().lower() != cand_status:
                    continue

            location_val = r.get("location") or contact_info.get("location")
            job_title_val = r.get("job_title") or contact_info.get("job_title") or best_match.get("job_title")
            company_val = r.get("company_name") or r.get("company") or contact_info.get("company_name") or contact_info.get("company")

            raw_fc = r.get("field_confidence") or contact_info.get("field_confidence") or {}
            raw_fct = r.get("field_confidence_tiers") or contact_info.get("field_confidence_tiers") or {}

            name_tier = r.get("name_confidence_tier") or raw_fct.get("name") or contact_info.get("name_confidence_level") or RuleConfigManager.get_confidence_tier("name", r.get("name_confidence") or raw_fc.get("name"))
            loc_tier = r.get("location_confidence_tier") or raw_fct.get("location") or RuleConfigManager.get_confidence_tier("location", r.get("location_confidence") or raw_fc.get("location"))
            title_tier = r.get("job_title_confidence_tier") or raw_fct.get("job_title") or RuleConfigManager.get_confidence_tier("job_title", r.get("job_title_confidence") or raw_fc.get("job_title"))
            comp_tier = r.get("company_name_confidence_tier") or raw_fct.get("company_name") or RuleConfigManager.get_confidence_tier("company_name", r.get("company_name_confidence") or raw_fc.get("company_name"))

            fct = {
                "name": name_tier if extracted_name and extracted_name.lower() != "unknown candidate" else "LOW",
                "location": loc_tier if location_val else "LOW",
                "job_title": title_tier if job_title_val else "LOW",
                "company_name": comp_tier if company_val else "LOW",
            }

            items.append(
                CandidateSearchResultItem(
                    id=r.get("id") or cv_key,
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
                    primary_department=match_analysis.get("primary_department"),
                    similarity_score=sim_score,
                    search_mode=search_mode,
                    best_match={
                        "job_title": best_match.get("job_title"),
                        "department": best_match.get("department") or best_match.get("department_name"),
                        "score": best_match.get("score") or best_match.get("overall_score"),
                        "classification": best_match.get("classification"),
                        "recommendation": best_match.get("recommendation"),
                        "domain_mismatch_capped": best_match.get("domain_mismatch_capped") or any(
                            (f.get("requirement_id") == "req_domain_mismatch" if isinstance(f, dict) else False)
                            for f in (best_match.get("mandatory_failures") or best_match.get("mandatory_fails") or [])
                        ),
                        "domain_mismatch_reason": best_match.get("domain_mismatch_reason"),
                        "retrieval_source": best_match.get("retrieval_source"),
                    },
                )
            )

        # Sort results: Semantic mode sorts by similarity_score descending
        if search_mode == "semantic":
            items.sort(key=lambda x: x.similarity_score or 0.0, reverse=True)

        total_found = len(items)
        paginated_items = items[: request.limit]

        return CandidateSearchResponse(
            total_found=total_found,
            search_mode=search_mode,
            query=request.query,
            candidates=paginated_items,
        )
