-- Migration Rollback: 001_init_cvai_schema_down.sql
-- Description: Drops cvai core tracking tables in reverse dependency order.

IF OBJECT_ID('cvai.match_results_history', 'U') IS NOT NULL DROP TABLE cvai.match_results_history;
GO
IF OBJECT_ID('cvai.match_results', 'U') IS NOT NULL DROP TABLE cvai.match_results;
GO
IF OBJECT_ID('cvai.candidates', 'U') IS NOT NULL DROP TABLE cvai.candidates;
GO
IF OBJECT_ID('cvai.cv_documents', 'U') IS NOT NULL DROP TABLE cvai.cv_documents;
GO
