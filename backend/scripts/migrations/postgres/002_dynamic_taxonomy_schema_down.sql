-- Migration Rollback: 002_dynamic_taxonomy_schema_down.sql (PostgreSQL)
-- Description: Drops dynamic taxonomy tables in reverse dependency order.

DROP TABLE IF EXISTS cvai.family_compatibilities CASCADE;
DROP TABLE IF EXISTS cvai.designation_skills CASCADE;
DROP TABLE IF EXISTS cvai.skills CASCADE;
DROP TABLE IF EXISTS cvai.designation_synonyms CASCADE;
DROP TABLE IF EXISTS cvai.designations CASCADE;
DROP TABLE IF EXISTS cvai.job_families CASCADE;
DROP TABLE IF EXISTS cvai.domains CASCADE;
