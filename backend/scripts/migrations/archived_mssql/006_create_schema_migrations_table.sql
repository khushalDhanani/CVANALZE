-- Migration: 006_create_schema_migrations_table.sql
-- Description: Creates the cvai.schema_migrations tracking table to record executed migration files, timestamps, and checksums.

IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'cvai')
BEGIN
    EXEC('CREATE SCHEMA cvai');
END
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.schema_migrations'))
BEGIN
    CREATE TABLE cvai.schema_migrations (
        version VARCHAR(50) PRIMARY KEY,
        migration_name VARCHAR(255) NOT NULL,
        applied_at DATETIME2 DEFAULT CURRENT_TIMESTAMP,
        checksum VARCHAR(64)
    );
END
GO
