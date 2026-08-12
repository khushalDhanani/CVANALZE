-- Migration: 020_add_department_name_snapshot_down.sql (PostgreSQL)

ALTER TABLE "DepartmentDomainMaster" DROP COLUMN IF EXISTS "DepartmentNameSnapshot";
