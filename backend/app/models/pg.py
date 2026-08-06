from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Index, Integer, String
from sqlalchemy.sql import func

from app.core.database import PostgresAppBase


class VacancyEmbedding(PostgresAppBase):
    __tablename__ = "vacancy_embeddings"

    vacancy_id = Column(Integer, primary_key=True)
    embedding = Column(Vector(768), nullable=True)
    embedding_model_version = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    tenant_id = Column(Integer, nullable=True)  # Unused for now
    source_snapshot = Column(String, nullable=True)  # JSON dump of the source payload
    source_watermark = Column(DateTime(timezone=True), nullable=True)  # Source system last updated timestamp
    freshness_status = Column(String, default="FRESH", nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index(
            "ix_vacancy_embeddings_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class CandidateEmbedding(PostgresAppBase):
    __tablename__ = "candidate_embeddings"

    cv_key = Column(String, primary_key=True)
    embedding = Column(Vector(768), nullable=True)
    embedding_model_version = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    source_snapshot = Column(String, nullable=True)  # JSON dump of the source payload
    source_watermark = Column(DateTime(timezone=True), nullable=True)  # Source system last updated timestamp
    freshness_status = Column(String, default="FRESH", nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index(
            "ix_candidate_embeddings_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class DomainEmbedding(PostgresAppBase):
    __tablename__ = "domain_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String, nullable=False, index=True)
    term = Column(String, nullable=False, index=True)
    embedding = Column(Vector(768), nullable=True)
    embedding_model_version = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index(
            "ix_domain_embeddings_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
class DepartmentAliasMapping(PostgresAppBase):
    """Mapping from internal department/designation names to industry‑standard labels.

    Used by DepartmentNormalizer to translate internal taxonomy identifiers to
    normalized industry labels. Optional ``department_id`` can be linked to a
    Department master table when needed.
    """
    __tablename__ = "department_alias_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    internal_name = Column(String, nullable=False, unique=True)
    industry_label = Column(String, nullable=False)
    department_id = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_department_alias_internal_name", "internal_name"),
    )

