-- Migration Rollback: 032_dynamic_hybrid_search_architecture_down.sql (PostgreSQL)
-- Description: Drops candidate_search_documents and candidate_section_embeddings tables and indexes.

DROP INDEX IF EXISTS ix_candidate_search_docs_trgm;
DROP INDEX IF EXISTS ix_candidate_search_docs_fts;
DROP TABLE IF EXISTS candidate_search_documents;

DROP INDEX IF EXISTS ix_candidate_section_embeddings_embedding;
DROP INDEX IF EXISTS ix_candidate_section_embeddings_section_type;
DROP INDEX IF EXISTS ix_candidate_section_embeddings_cv_key;
DROP TABLE IF EXISTS candidate_section_embeddings;
