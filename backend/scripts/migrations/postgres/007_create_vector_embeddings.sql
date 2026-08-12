-- Migration: 007_create_vector_embeddings.sql (PostgreSQL)
-- Description: Creates the pgvector extension and embedding tables formerly created by SQLAlchemy startup initialization.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS vacancy_embeddings (
    vacancy_id INTEGER PRIMARY KEY,
    embedding VECTOR(768),
    embedding_model_version VARCHAR,
    content_hash VARCHAR,
    tenant_id INTEGER,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS candidate_embeddings (
    cv_key VARCHAR PRIMARY KEY,
    embedding VECTOR(768),
    embedding_model_version VARCHAR,
    content_hash VARCHAR,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS domain_embeddings (
    id SERIAL PRIMARY KEY,
    category VARCHAR NOT NULL,
    term VARCHAR NOT NULL,
    embedding VECTOR(768),
    embedding_model_version VARCHAR,
    content_hash VARCHAR,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_vacancy_embeddings_embedding
    ON vacancy_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_candidate_embeddings_embedding
    ON candidate_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_domain_embeddings_embedding
    ON domain_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_domain_embeddings_category ON domain_embeddings (category);
CREATE INDEX IF NOT EXISTS ix_domain_embeddings_term ON domain_embeddings (term);
