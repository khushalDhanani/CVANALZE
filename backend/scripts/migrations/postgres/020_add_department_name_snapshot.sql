-- Migration: 020_add_department_name_snapshot.sql (PostgreSQL)
-- Description: Adds the DepartmentNameSnapshot column to DepartmentDomainMaster
-- which was introduced in the model but omitted by migration 005. Without it the
-- department domain loader fails with: column DepartmentDomainMaster.DepartmentNameSnapshot does not exist.

ALTER TABLE "DepartmentDomainMaster" ADD COLUMN IF NOT EXISTS "DepartmentNameSnapshot" VARCHAR(200);

CREATE INDEX IF NOT EXISTS "IX_DepartmentDomainMaster_DepartmentNameSnapshot" ON "DepartmentDomainMaster" ("DepartmentNameSnapshot");
