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
    def get_or_generate_domain_embedding(cls, term: str, category: str, allow_live_generation: bool = True) -> list[float] | None:
        if not term or not term.strip():
            return None

        clean_term = term.strip().lower()
        return cls.get_or_generate_domain_embeddings(
            [clean_term],
            category,
            allow_live_generation=allow_live_generation,
        ).get(clean_term)

    @classmethod
    def get_or_generate_domain_embeddings(
        cls,
        terms: list[str],
        category: str,
        allow_live_generation: bool = True,
    ) -> dict[str, list[float]]:
        """Resolve related domain terms through one cached, serialized Ollama batch."""
        cat = category.strip().lower()
        clean_terms = list(dict.fromkeys(term.strip().lower() for term in terms if term and term.strip()))
        resolved: dict[str, list[float]] = {}
        pending: list[str] = []

        for clean_term in clean_terms:
            stored = cls._load_domain_embedding(clean_term, cat)
            if stored is not None:
                resolved[clean_term] = stored
            elif allow_live_generation:
                pending.append(clean_term)

        if not allow_live_generation:
            for clean_term in clean_terms:
                if clean_term not in resolved:
                    logger.debug(f"[DOMAIN_EMBEDDING] Live generation disabled for '{clean_term}' ({cat}). Returning None.")
            return resolved

        if pending:
            model_version = settings.EMBEDDING_MODEL
            generated = EmbeddingService.generate_batch_embeddings(
                pending,
                model_version=model_version,
                identifiers=[f"domain:{cat}:{term}" for term in pending],
            )
            for index, clean_term in enumerate(pending):
                embedding = generated.get(str(index))
                if embedding:
                    resolved[clean_term] = embedding
                    cls._save_domain_embedding(clean_term, cat, embedding, model_version)
        return resolved

    @staticmethod
    def _load_domain_embedding(clean_term: str, category: str) -> list[float] | None:
        try:
            from app.core.database import PostgresAppSession
            from app.models.pg import DomainEmbedding

            if PostgresAppSession is not None:
                with PostgresAppSession() as session:
                    stmt = select(DomainEmbedding.embedding).where(
                        DomainEmbedding.category == category,
                        DomainEmbedding.term == clean_term,
                    )
                    embedding = session.execute(stmt).scalar_one_or_none()
                    if embedding is not None:
                        return list(embedding)
        except Exception as exc:
            logger.warning(f"[DOMAIN_EMBEDDING] DB lookup failed for '{clean_term}': {exc}")
        return None

    @staticmethod
    def _save_domain_embedding(clean_term: str, category: str, embedding: list[float], model_version: str) -> None:
        try:
            from app.core.database import PostgresAppSession
            from app.models.pg import DomainEmbedding

            if PostgresAppSession is None:
                return
            content_hash = hashlib.sha256(clean_term.encode("utf-8")).hexdigest()
            with PostgresAppSession() as session:
                rec = DomainEmbedding(
                    category=category,
                    term=clean_term,
                    embedding=embedding,
                    embedding_model_version=model_version,
                    content_hash=content_hash,
                )
                session.add(rec)
                session.commit()
        except Exception as exc:
            logger.warning(f"[DOMAIN_EMBEDDING] DB persistence failed for '{clean_term}': {exc}")

    @classmethod
    def find_semantic_equivalents(
        cls,
        term: str,
        category: str = "skills",
        threshold: float = 0.82,
        limit: int = 5,
        allow_live_generation: bool = True,
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
            equivalents.append(
                {
                    "term": eq_term,
                    "similarity_score": 0.98,
                    "category": cat,
                    "source": "canonical_rules",
                }
            )

        for alias, canon in canonical_map.items():
            if canon == clean_term and alias != clean_term:
                equivalents.append(
                    {
                        "term": alias,
                        "similarity_score": 0.98,
                        "category": cat,
                        "source": "canonical_rules",
                    }
                )

        # 2. Vector distance query in PostgreSQL pgvector
        target_emb = cls.get_or_generate_domain_embedding(clean_term, cat, allow_live_generation=allow_live_generation)
        if target_emb:
            try:
                from app.core.database import PostgresAppSession
                from app.models.pg import DomainEmbedding

                if PostgresAppSession is not None:
                    with PostgresAppSession() as session:
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
                                equivalents.append(
                                    {
                                        "term": other_term,
                                        "similarity_score": sim,
                                        "category": cat,
                                        "source": "vector_similarity",
                                    }
                                )
            except Exception as exc:
                logger.warning(f"[DOMAIN_EMBEDDING] Vector equivalent query failed: {exc}")

        equivalents.sort(key=lambda x: x.get("similarity_score", 0.0), reverse=True)
        return equivalents[:limit]

    @classmethod
    def expand_skills_with_semantic_equivalents(cls, skills: list[str], threshold: float = 0.82) -> set[str]:
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

        embeddings = cls.get_or_generate_domain_embeddings([job_title, candidate_title], "job_titles")
        t1_emb = embeddings.get(job_title.strip().lower())
        t2_emb = embeddings.get(candidate_title.strip().lower())

        if t1_emb and t2_emb:
            return round(EmbeddingService.cosine_similarity(t1_emb, t2_emb), 4)

        return 0.0
