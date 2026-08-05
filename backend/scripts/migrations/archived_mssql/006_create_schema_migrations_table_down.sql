-- Migration Rollback: 006_create_schema_migrations_table_down.sql
-- Description: Drops cvai.schema_migrations tracking table.

IF OBJECT_ID('cvai.schema_migrations', 'U') IS NOT NULL DROP TABLE cvai.schema_migrations;
GO
