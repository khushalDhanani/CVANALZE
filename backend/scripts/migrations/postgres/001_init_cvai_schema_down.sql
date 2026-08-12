-- Migration Rollback: 001_init_cvai_schema_down.sql (PostgreSQL)
-- Description: Drops cvai core tracking tables in reverse dependency order.

DROP TABLE IF EXISTS cvai.match_results_history CASCADE;
DROP TABLE IF EXISTS cvai.match_results CASCADE;
DROP TABLE IF EXISTS cvai.candidates CASCADE;
DROP TABLE IF EXISTS cvai.cv_documents CASCADE;
