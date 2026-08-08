-- Migration 018 Down: Rollback generation_sequence column and sequence idempotently

-- 1. Drop index first
DROP INDEX IF EXISTS idx_cv_results_generation_sequence;

-- 2. Drop column default (if column exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'cv_results' AND column_name = 'generation_sequence'
    ) THEN
        ALTER TABLE cv_results ALTER COLUMN generation_sequence DROP DEFAULT;
    END IF;
END $$;

-- 3. Drop generation_sequence column from cv_results
ALTER TABLE cv_results DROP COLUMN IF NOT EXISTS generation_sequence;

-- 4. Drop sequence
DROP SEQUENCE IF EXISTS cv_results_generation_seq;
