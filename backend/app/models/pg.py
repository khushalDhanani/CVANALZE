from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.core.database import pg_Base


class VacancyEmbedding(pg_Base):
    __tablename__ = "vacancy_embeddings"

    vacancy_id = Column(Integer, primary_key=True)
    embedding = Column(Vector(768), nullable=True)
    embedding_model_version = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    tenant_id = Column(Integer, nullable=True)  # Unused for now
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


class CandidateEmbedding(pg_Base):
    __tablename__ = "candidate_embeddings"

    cv_key = Column(String, primary_key=True)
    embedding = Column(Vector(768), nullable=True)
    embedding_model_version = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
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


class DomainEmbedding(pg_Base):
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


