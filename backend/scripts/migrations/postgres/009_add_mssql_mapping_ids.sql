-- Migration: 009_add_mssql_mapping_ids.sql
ALTER TABLE cvai.job_families ADD COLUMN mssql_department_id INTEGER NULL;
ALTER TABLE cvai.designations ADD COLUMN mssql_designation_id INTEGER NULL;
