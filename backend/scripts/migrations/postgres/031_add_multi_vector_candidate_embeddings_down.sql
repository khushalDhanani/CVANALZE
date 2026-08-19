-- Migration Rollback: 031_add_multi_vector_candidate_embeddings_down.sql (PostgreSQL)
-- Description: Drops section vector indexes and columns from candidate_embeddings table.

DROP INDEX IF EXISTS ix_candidate_embeddings_domain;
DROP INDEX IF EXISTS ix_candidate_embeddings_projects;
DROP INDEX IF EXISTS ix_candidate_embeddings_experience;
DROP INDEX IF EXISTS ix_candidate_embeddings_skills;
DROP INDEX IF EXISTS ix_candidate_embeddings_profile;

ALTER TABLE candidate_embeddings
    DROP COLUMN IF EXISTS domain_embedding,
    DROP COLUMN IF EXISTS projects_embedding,
    DROP COLUMN IF EXISTS experience_embedding,
    DROP COLUMN IF EXISTS skills_embedding,
    DROP COLUMN IF EXISTS profile_embedding;
