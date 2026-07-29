from sqlalchemy import Column, BigInteger, String, DateTime, Index
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.core.database import pg_Base

class VacancyEmbedding(pg_Base):
    __tablename__ = "vacancy_embeddings"

    id = Column(BigInteger, primary_key=True, index=True)
    vacancy_id = Column(BigInteger, unique=True, index=True, nullable=False)
    content_hash = Column(String, index=True)
    # nomic-embed-text generates 768 dimensional embeddings
    embedding = Column(Vector(768))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    __table_args__ = (
        Index('ix_vacancy_embeddings_embedding', 
              'embedding', 
              postgresql_using='hnsw', 
              postgresql_with={'m': 16, 'ef_construction': 64}, 
              postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )
