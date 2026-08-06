-- Migration: 010_remove_hardcoded_seeds.sql
DELETE FROM "DepartmentDomainMaster" WHERE "DepartmentId" IS NULL;
