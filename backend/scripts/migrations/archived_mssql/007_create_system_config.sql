-- Migration: 007_create_system_config.sql (MSSQL)
-- Description: Creates the runtime matching configuration table formerly created by SQLAlchemy startup initialization.

IF OBJECT_ID('dbo.system_config', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.system_config (
        setting_key NVARCHAR(100) NOT NULL PRIMARY KEY,
        setting_value NVARCHAR(500) NOT NULL,
        updated_at DATETIME2 NULL
    );
END;
