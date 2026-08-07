-- Migration Reversal: 017_add_embedding_source_metadata_columns_down.sql (PostgreSQL)
-- Description: Drops source_snapshot, source_watermark, and freshness_status columns from candidate_embeddings and vacancy_embeddings tables.

ALTER TABLE candidate_embeddings DROP COLUMN IF EXISTS freshness_status;
ALTER TABLE candidate_embeddings DROP COLUMN IF EXISTS source_watermark;
ALTER TABLE candidate_embeddings DROP COLUMN IF EXISTS source_snapshot;

ALTER TABLE vacancy_embeddings DROP COLUMN IF EXISTS freshness_status;
ALTER TABLE vacancy_embeddings DROP COLUMN IF EXISTS source_watermark;
ALTER TABLE vacancy_embeddings DROP COLUMN IF EXISTS source_snapshot;
