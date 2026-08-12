-- Migration: 017_add_embedding_source_metadata_columns.sql (PostgreSQL)
-- Description: Adds missing source_snapshot, source_watermark, and freshness_status metadata columns to candidate_embeddings and vacancy_embeddings tables.

ALTER TABLE candidate_embeddings ADD COLUMN IF NOT EXISTS source_snapshot VARCHAR;
ALTER TABLE candidate_embeddings ADD COLUMN IF NOT EXISTS source_watermark TIMESTAMP WITH TIME ZONE;
ALTER TABLE candidate_embeddings ADD COLUMN IF NOT EXISTS freshness_status VARCHAR NOT NULL DEFAULT 'FRESH';

ALTER TABLE vacancy_embeddings ADD COLUMN IF NOT EXISTS source_snapshot VARCHAR;
ALTER TABLE vacancy_embeddings ADD COLUMN IF NOT EXISTS source_watermark TIMESTAMP WITH TIME ZONE;
ALTER TABLE vacancy_embeddings ADD COLUMN IF NOT EXISTS freshness_status VARCHAR NOT NULL DEFAULT 'FRESH';
