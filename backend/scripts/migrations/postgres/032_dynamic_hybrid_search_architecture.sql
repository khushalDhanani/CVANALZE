-- Migration: 032_dynamic_hybrid_search_architecture.sql (PostgreSQL)
-- Description: Creates candidate_section_embeddings and candidate_search_documents tables with pg_trgm extension, GIN FTS/trigram indexes, and HNSW section indexes.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS candidate_section_embeddings (
    id SERIAL PRIMARY KEY,
    cv_key VARCHAR NOT NULL,
    section_type VARCHAR NOT NULL,
    embedding VECTOR(768),
    embedding_model_version VARCHAR NOT NULL,
    content_hash VARCHAR,
    freshness_status VARCHAR DEFAULT 'FRESH' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uix_cv_key_section_type UNIQUE (cv_key, section_type)
);

CREATE INDEX IF NOT EXISTS ix_candidate_section_embeddings_cv_key
    ON candidate_section_embeddings (cv_key);

CREATE INDEX IF NOT EXISTS ix_candidate_section_embeddings_section_type
    ON candidate_section_embeddings (section_type);

CREATE INDEX IF NOT EXISTS ix_candidate_section_embeddings_embedding
    ON candidate_section_embeddings USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE TABLE IF NOT EXISTS candidate_search_documents (
    cv_key VARCHAR PRIMARY KEY,
    search_document TSVECTOR,
    content_snapshot TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_candidate_search_docs_fts
    ON candidate_search_documents USING gin (search_document);

CREATE INDEX IF NOT EXISTS ix_candidate_search_docs_trgm
    ON candidate_search_documents USING gin (content_snapshot gin_trgm_ops);
