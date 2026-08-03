-- Migration Rollback: 007_create_vector_embeddings_down.sql (PostgreSQL)
-- Description: Drops application embedding tables while retaining the shared vector extension.

DROP TABLE IF EXISTS domain_embeddings;
DROP TABLE IF EXISTS candidate_embeddings;
DROP TABLE IF EXISTS vacancy_embeddings;
