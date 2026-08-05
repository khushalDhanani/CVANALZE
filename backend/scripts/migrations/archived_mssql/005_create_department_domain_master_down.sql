-- Migration Rollback: 005_create_department_domain_master_down.sql
-- Description: Drops DepartmentDomainMaster table and associated foreign key constraints.

IF EXISTS (
    SELECT * FROM sys.foreign_keys 
    WHERE name = N'FK_DepartmentDomainMaster_Department'
      AND parent_object_id = OBJECT_ID(N'dbo.DepartmentDomainMaster')
)
BEGIN
    ALTER TABLE dbo.DepartmentDomainMaster DROP CONSTRAINT FK_DepartmentDomainMaster_Department;
END
GO

IF OBJECT_ID('dbo.DepartmentDomainMaster', 'U') IS NOT NULL DROP TABLE dbo.DepartmentDomainMaster;
GO
