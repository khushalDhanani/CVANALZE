-- Migration: 031_add_multi_vector_candidate_embeddings.sql (PostgreSQL)
-- Description: Adds section-specific vector columns (profile, skills, experience, projects, domain) with HNSW cosine indexes to candidate_embeddings table.

ALTER TABLE candidate_embeddings
    ADD COLUMN IF NOT EXISTS profile_embedding VECTOR(768),
    ADD COLUMN IF NOT EXISTS skills_embedding VECTOR(768),
    ADD COLUMN IF NOT EXISTS experience_embedding VECTOR(768),
    ADD COLUMN IF NOT EXISTS projects_embedding VECTOR(768),
    ADD COLUMN IF NOT EXISTS domain_embedding VECTOR(768);

CREATE INDEX IF NOT EXISTS ix_candidate_embeddings_profile
    ON candidate_embeddings USING hnsw (profile_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_candidate_embeddings_skills
    ON candidate_embeddings USING hnsw (skills_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_candidate_embeddings_experience
    ON candidate_embeddings USING hnsw (experience_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_candidate_embeddings_projects
    ON candidate_embeddings USING hnsw (projects_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS ix_candidate_embeddings_domain
    ON candidate_embeddings USING hnsw (domain_embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
