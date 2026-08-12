-- Migration Rollback: 003_geo_and_headers_schema_down.sql (PostgreSQL)
-- Description: Drops geo locations, section headings, and name denylists tables.

DROP TABLE IF EXISTS cvai.name_denylists CASCADE;
DROP TABLE IF EXISTS cvai.section_headings CASCADE;
DROP TABLE IF EXISTS cvai.geo_locations CASCADE;
