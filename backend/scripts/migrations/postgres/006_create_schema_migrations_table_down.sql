-- Migration Rollback: 006_create_schema_migrations_table_down.sql (PostgreSQL)
-- Description: Drops cvai.schema_migrations tracking table.

DROP TABLE IF EXISTS cvai.schema_migrations CASCADE;
