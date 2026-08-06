-- 011_create_cv_results_table_down.sql

DROP INDEX IF EXISTS cvai.ix_cv_results_parsed_at;
DROP INDEX IF EXISTS cvai.ix_cv_results_cv_hash;
DROP TABLE IF EXISTS cvai.cv_results;
