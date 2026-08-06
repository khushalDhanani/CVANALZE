-- -----------------------------------------------------------------------------------
-- MSSQL Script: 002_drop_cvai_schema.sql
-- Description: CAUTION! This script completely drops the 'cvai' schema and all 
--              its associated tables from the MSSQL database. 
--              Only execute this after the PostgreSQL cutover has been fully stabilized.
-- -----------------------------------------------------------------------------------

USE AIRIS_TEST; -- Replace with your actual DB Name if different
GO

PRINT '=========================================================';
PRINT '  WARNING: Preparing to DROP the cvai schema             ';
PRINT '=========================================================';

-- Step 1: Drop tables in the correct order to respect Foreign Keys (if any existed inside cvai)
IF OBJECT_ID('cvai.cv_results', 'U') IS NOT NULL
BEGIN
    DROP TABLE cvai.cv_results;
    PRINT 'Dropped table cvai.cv_results';
END

-- Drop other cvai tables if they were created (e.g. cvai.cv_cache, etc)
-- IF OBJECT_ID('cvai.cv_cache', 'U') IS NOT NULL
-- BEGIN
--     DROP TABLE cvai.cv_cache;
--     PRINT 'Dropped table cvai.cv_cache';
-- END

-- Step 2: Drop the schema itself
IF EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'cvai')
BEGIN
    DROP SCHEMA cvai;
    PRINT 'Dropped schema cvai';
END
ELSE
BEGIN
    PRINT 'Schema cvai does not exist.';
END

PRINT '=========================================================';
PRINT '  cvai schema successfully dropped.                      ';
PRINT '=========================================================';
