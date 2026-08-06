-- Migration: 005_create_department_domain_master.sql (PostgreSQL)
-- Description: Creates DepartmentDomainMaster table and seeds initial domain mappings for PostgreSQL.

CREATE TABLE IF NOT EXISTS "DepartmentDomainMaster" (
    "Id" BIGSERIAL PRIMARY KEY,
    "DepartmentId" BIGINT,
    "DomainName" VARCHAR(200) NOT NULL,
    "Keywords" JSONB NOT NULL,
    "DefaultRoles" JSONB NOT NULL,
    "Priority" INT NOT NULL DEFAULT 0,
    "IsActive" BOOLEAN NOT NULL DEFAULT TRUE,
    "CreatedOn" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ModifiedOn" TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS "IX_DepartmentDomainMaster_DepartmentId" ON "DepartmentDomainMaster" ("DepartmentId");
CREATE INDEX IF NOT EXISTS "IX_DepartmentDomainMaster_IsActive" ON "DepartmentDomainMaster" ("IsActive");


