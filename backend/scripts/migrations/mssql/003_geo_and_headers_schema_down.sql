-- Migration Rollback: 003_geo_and_headers_schema_down.sql
-- Description: Drops geo locations, section headings, and name denylists tables.

IF OBJECT_ID('cvai.name_denylists', 'U') IS NOT NULL DROP TABLE cvai.name_denylists;
GO
IF OBJECT_ID('cvai.section_headings', 'U') IS NOT NULL DROP TABLE cvai.section_headings;
GO
IF OBJECT_ID('cvai.geo_locations', 'U') IS NOT NULL DROP TABLE cvai.geo_locations;
GO
