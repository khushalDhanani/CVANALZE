-- Migration: 009_add_mssql_mapping_ids_down.sql
ALTER TABLE cvai.job_families DROP COLUMN mssql_department_id;
ALTER TABLE cvai.designations DROP COLUMN mssql_designation_id;
