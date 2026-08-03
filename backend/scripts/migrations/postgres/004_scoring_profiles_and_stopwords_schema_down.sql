-- Migration Rollback: 004_scoring_profiles_and_stopwords_schema_down.sql (PostgreSQL)
-- Description: Drops scoring profiles and stop words tables.

DROP TABLE IF EXISTS cvai.scoring_profiles CASCADE;
DROP TABLE IF EXISTS cvai.stop_words CASCADE;
