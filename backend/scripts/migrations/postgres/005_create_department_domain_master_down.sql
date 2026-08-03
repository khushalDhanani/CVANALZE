-- Migration Rollback: 005_create_department_domain_master_down.sql (PostgreSQL)
-- Description: Drops DepartmentDomainMaster table.

DROP TABLE IF EXISTS "DepartmentDomainMaster" CASCADE;
