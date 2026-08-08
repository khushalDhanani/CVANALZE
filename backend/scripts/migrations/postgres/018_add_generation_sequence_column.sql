-- Migration 018: Add DB-backed monotonic generation sequence to cv_results table

-- 1. Create PostgreSQL sequence for monotonic generation sequence
CREATE SEQUENCE IF NOT EXISTS cv_results_generation_seq START WITH 1 INCREMENT BY 1;

-- 2. Add generation_sequence column to cv_results table
ALTER TABLE cv_results ADD COLUMN IF NOT EXISTS generation_sequence BIGINT DEFAULT nextval('cv_results_generation_seq');

-- 3. Safely backfill existing null rows
UPDATE cv_results 
SET generation_sequence = nextval('cv_results_generation_seq') 
WHERE generation_sequence IS NULL;

-- 4. Set default sequence generator on column
ALTER TABLE cv_results ALTER COLUMN generation_sequence SET DEFAULT nextval('cv_results_generation_seq');

-- 5. Create index on generation_sequence
CREATE INDEX IF NOT EXISTS idx_cv_results_generation_sequence ON cv_results(generation_sequence);
