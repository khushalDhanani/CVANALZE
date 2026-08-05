-- Migration Rollback: 002_dynamic_taxonomy_schema_down.sql
-- Description: Drops dynamic taxonomy tables in reverse dependency order.

IF OBJECT_ID('cvai.family_compatibilities', 'U') IS NOT NULL DROP TABLE cvai.family_compatibilities;
GO
IF OBJECT_ID('cvai.designation_skills', 'U') IS NOT NULL DROP TABLE cvai.designation_skills;
GO
IF OBJECT_ID('cvai.skills', 'U') IS NOT NULL DROP TABLE cvai.skills;
GO
IF OBJECT_ID('cvai.designation_synonyms', 'U') IS NOT NULL DROP TABLE cvai.designation_synonyms;
GO
IF OBJECT_ID('cvai.designations', 'U') IS NOT NULL DROP TABLE cvai.designations;
GO
IF OBJECT_ID('cvai.job_families', 'U') IS NOT NULL DROP TABLE cvai.job_families;
GO
IF OBJECT_ID('cvai.domains', 'U') IS NOT NULL DROP TABLE cvai.domains;
GO
