-- Migration Rollback: 007_create_system_config_down.sql (MSSQL)
-- Description: Drops the runtime matching configuration table.

IF OBJECT_ID('dbo.system_config', 'U') IS NOT NULL
BEGIN
    DROP TABLE dbo.system_config;
END;
