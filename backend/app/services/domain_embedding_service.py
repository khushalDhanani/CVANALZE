import hashlib
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.core.rule_config_manager import RuleConfigManager
from app.services.embedding_service import EmbeddingService


class classproperty:
    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        return self.func(owner)


class DomainEmbeddingService:
    """
    Domain Knowledge Embedding Service across 8 enterprise categories:
    - skills, job_titles, departments, technologies, certifications, education_domains, industries, functional_areas.
    Enables semantic equivalence and role relationship resolution while keeping deterministic validation
    as the strict source of truth for mandatory requirements.
    Categories and canonical equivalents are data-driven from the scoring.domain_embedding
    section in rule_config.json.
    """

    @classproperty
    def CATEGORIES(cls) -> set[str]:
        return set(RuleConfigManager.get_domain_embedding_rules().categories)

    @classproperty
    def CANONICAL_EQUIVALENTS(cls) -> dict[str, dict[str, str]]:
        return dict(RuleConfigManager.get_domain_embedding_rules().canonical_equivalents)

    @classmethod
    def get_or_generate_domain_embedding(cls, term: str, category: str) -> list[float] | None:
        if not term or not term.strip():
            return None

        clean_term = term.strip().lower()
        cat = category.strip().lower()

        model_version = settings.EMBEDDING_MODEL

        # 1. DB Lookup in PostgreSQL domain_embeddings table
        try:
            from app.core.database import pg_SessionLocal
            from app.models.pg import DomainEmbedding

            if pg_SessionLocal is not None:
                with pg_SessionLocal() as session:
                    stmt = select(DomainEmbedding.embedding).where(
                        DomainEmbedding.category == cat,
                        DomainEmbedding.term == clean_term,
                    )
                    emb = session.execute(stmt).scalar_one_or_none()
                    if emb is not None:
                        return list(emb)
        except Exception as exc:
            logger.warning(f"[DOMAIN_EMBEDDING] DB lookup failed for '{clean_term}': {exc}")

        # 2. Generate embedding via EmbeddingService if missing
        try:
            emb = EmbeddingService.generate_embedding(
                clean_term, model_version=model_version, identifier=f"domain:{cat}:{clean_term}"
            )
            if emb and pg_SessionLocal is not None:
                content_hash = hashlib.sha256(clean_term.encode("utf-8")).hexdigest()
                with pg_SessionLocal() as session:
                    rec = DomainEmbedding(
                        category=cat,
                        term=clean_term,
                        embedding=emb,
                        embedding_model_version=model_version,
                        content_hash=content_hash,
                    )
                    session.add(rec)
                    session.commit()
            return emb
        except Exception as exc:
            logger.warning(f"[DOMAIN_EMBEDDING] Generation failed for '{clean_term}': {exc}")
            return None

    @classmethod
    def find_semantic_equivalents(
        cls, term: str, category: str = "skills", threshold: float = 0.82, limit: int = 5
    ) -> list[dict[str, Any]]:
        if not term or not term.strip():
            return []

        clean_term = term.strip().lower()
        cat = category.strip().lower()

        equivalents: list[dict[str, Any]] = []

        # 1. Check built-in canonical equivalents map first
        canonical_map = cls.CANONICAL_EQUIVALENTS.get(cat, {})
        if clean_term in canonical_map:
            eq_term = canonical_map[clean_term]
            equivalents.append({
                "term": eq_term,
                "similarity_score": 0.98,
                "category": cat,
                "source": "canonical_rules",
            })

        for alias, canon in canonical_map.items():
            if canon == clean_term and alias != clean_term:
                equivalents.append({
                    "term": alias,
                    "similarity_score": 0.98,
                    "category": cat,
                    "source": "canonical_rules",
                })

        # 2. Vector distance query in PostgreSQL pgvector
        target_emb = cls.get_or_generate_domain_embedding(clean_term, cat)
        if target_emb:
            try:
                from app.core.database import pg_SessionLocal
                from app.models.pg import DomainEmbedding

                if pg_SessionLocal is not None:
                    with pg_SessionLocal() as session:
                        stmt = (
                            select(
                                DomainEmbedding.term,
                                DomainEmbedding.embedding.cosine_distance(target_emb).label("distance"),
                            )
                            .where(
                                DomainEmbedding.category == cat,
                                DomainEmbedding.term != clean_term,
                            )
                            .order_by("distance")
                            .limit(limit * 2)
                        )
                        rows = session.execute(stmt).all()
                        for row in rows:
                            other_term = str(row.term)
                            dist = float(row.distance) if row.distance is not None else 1.0
                            sim = round(max(0.0, 1.0 - dist), 4)
                            if sim >= threshold and not any(e["term"] == other_term for e in equivalents):
                                equivalents.append({
                                    "term": other_term,
                                    "similarity_score": sim,
                                    "category": cat,
                                    "source": "vector_similarity",
                                })
            except Exception as exc:
                logger.warning(f"[DOMAIN_EMBEDDING] Vector equivalent query failed: {exc}")

        equivalents.sort(key=lambda x: x.get("similarity_score", 0.0), reverse=True)
        return equivalents[:limit]

    @classmethod
    def expand_skills_with_semantic_equivalents(
        cls, skills: list[str], threshold: float = 0.82
    ) -> set[str]:
        """
        Expands a list of skill strings into a set containing all original skills plus their semantic equivalents.
        """
        expanded = set()
        for s in skills:
            if not s or not isinstance(s, str):
                continue
            clean_s = s.strip().lower()
            expanded.add(clean_s)

            # Add canonical mapping if exists
            canonical_map = cls.CANONICAL_EQUIVALENTS.get("skills", {})
            if clean_s in canonical_map:
                expanded.add(canonical_map[clean_s])

            for alias, canon in canonical_map.items():
                if canon == clean_s:
                    expanded.add(alias)

        return expanded

    @classmethod
    def evaluate_semantic_role_similarity(cls, job_title: str, candidate_title: str) -> float:
        """
        Computes vector similarity score between job title and candidate role title.
        """
        if not job_title or not candidate_title:
            return 0.0

        if job_title.strip().lower() == candidate_title.strip().lower():
            return 1.0

        t1_emb = cls.get_or_generate_domain_embedding(job_title, "job_titles")
        t2_emb = cls.get_or_generate_domain_embedding(candidate_title, "job_titles")

        if t1_emb and t2_emb:
            return round(EmbeddingService.cosine_similarity(t1_emb, t2_emb), 4)

        return 0.0
