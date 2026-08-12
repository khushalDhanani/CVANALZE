-- Migration: 006_create_schema_migrations_table.sql (PostgreSQL)
-- Description: Creates schema migration execution tracking table in cvai schema.

CREATE SCHEMA IF NOT EXISTS cvai;

CREATE TABLE IF NOT EXISTS cvai.schema_migrations (
    version VARCHAR(50) PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64)
);
