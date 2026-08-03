-- Migration Rollback: 004_scoring_profiles_and_stopwords_schema_down.sql
-- Description: Drops scoring profiles and stop words tables.

IF OBJECT_ID('cvai.scoring_profiles', 'U') IS NOT NULL DROP TABLE cvai.scoring_profiles;
GO
IF OBJECT_ID('cvai.stop_words', 'U') IS NOT NULL DROP TABLE cvai.stop_words;
GO
