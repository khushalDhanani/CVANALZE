-- Migration: 002_create_department_domain_master.sql
-- Description: Creates the DepartmentDomainMaster table, the DB-driven source of
--              truth for candidate department/domain detection. Replaces the legacy
--              hardcoded DEPARTMENT_DOMAIN_MAP in ScoringEngine so new departments
--              can be onboarded via data rows only (no code/deploy).
--              Keywords and DefaultRoles are stored as JSON text.

IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID(N'dbo.DepartmentDomainMaster'))
BEGIN
    CREATE TABLE dbo.DepartmentDomainMaster (
        Id           BIGINT IDENTITY(1,1) NOT NULL,
        DepartmentId BIGINT NULL,
        DomainName   NVARCHAR(200) NOT NULL,
        Keywords     NVARCHAR(MAX) NOT NULL,
        DefaultRoles NVARCHAR(MAX) NOT NULL,
        Priority     INT NOT NULL DEFAULT 0,
        IsActive     BIT NOT NULL DEFAULT 1,
        CreatedOn    DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        ModifiedOn   DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_DepartmentDomainMaster PRIMARY KEY (Id)
    );

    CREATE INDEX IX_DepartmentDomainMaster_DepartmentId
        ON dbo.DepartmentDomainMaster (DepartmentId);
    CREATE INDEX IX_DepartmentDomainMaster_IsActive
        ON dbo.DepartmentDomainMaster (IsActive);
END
GO

-- Add FK only if the referenced department master table exists.
IF NOT EXISTS (
    SELECT * FROM sys.foreign_keys
    WHERE name = N'FK_DepartmentDomainMaster_Department'
      AND parent_object_id = OBJECT_ID(N'dbo.DepartmentDomainMaster')
)
AND EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID(N'dbo.OrgDepartmentMst'))
BEGIN
    ALTER TABLE dbo.DepartmentDomainMaster
        ADD CONSTRAINT FK_DepartmentDomainMaster_Department
        FOREIGN KEY (DepartmentId) REFERENCES dbo.OrgDepartmentMst (DeptID);
END
GO

-- Seed rows: resolve DepartmentId from OrgDepartmentMst by real department name.
-- Each domain links to the active department it recommends candidates to.
-- Healthcare has no corresponding real department in the org (chemical plant),
-- so it is seeded with NULL DepartmentId (linked later when a department exists).
IF NOT EXISTS (SELECT 1 FROM dbo.DepartmentDomainMaster)
BEGIN
    INSERT INTO dbo.DepartmentDomainMaster (DepartmentId, DomainName, Keywords, DefaultRoles, Priority, IsActive)
    SELECT d.DeptID, N'Information Technology & Software',
           N'["developer","engineer","software","flutter","react","frontend","backend","full stack","fullstack","python","java","javascript","typescript","dart","c#","dotnet","sql","api","mobile","ios","android","devops","cloud","aws","azure","docker","kubernetes","database","ui/ux","web","coding","code"]',
           N'["Software Developer","Full Stack Engineer","Frontend/Mobile Engineer","Backend Developer"]',
           1, 1
    FROM dbo.OrgDepartmentMst d WHERE d.DeptName = N'CIS Team';

    INSERT INTO dbo.DepartmentDomainMaster (DepartmentId, DomainName, Keywords, DefaultRoles, Priority, IsActive)
    SELECT d.DeptID, N'Finance & Accounting',
           N'["finance","financial","accounting","accountant","audit","tax","ca","cpa","cfa","tally","ledger","payroll","budgeting","forecasting","treasury","billing","valuation"]',
           N'["Financial Analyst","Accountant","Finance Manager","Audit Specialist"]',
           2, 1
    FROM dbo.OrgDepartmentMst d WHERE d.DeptName = N'Finance Team';

    INSERT INTO dbo.DepartmentDomainMaster (DepartmentId, DomainName, Keywords, DefaultRoles, Priority, IsActive)
    SELECT d.DeptID, N'Human Resources',
           N'["hr","human resources","recruitment","recruiter","talent acquisition","onboarding","employee relations","performance management","hrbp","payroll management","people operations"]',
           N'["HR Executive","Talent Acquisition Specialist","HR Generalist","Recruiter"]',
           3, 1
    FROM dbo.OrgDepartmentMst d WHERE d.DeptName = N'HR & IR Team';

    INSERT INTO dbo.DepartmentDomainMaster (DepartmentId, DomainName, Keywords, DefaultRoles, Priority, IsActive)
    SELECT d.DeptID, N'Plant & Maintenance Engineering',
           N'["plant","maintenance","mechanical","electrical","utility","instrumentation","boiler","hvac","plc","scada","equipment","preventive maintenance","technician","machinery","fabrication"]',
           N'["Plant Maintenance Engineer","Maintenance Technician","Mechanical Engineer","Plant Assistant"]',
           4, 1
    FROM dbo.OrgDepartmentMst d WHERE d.DeptName = N'Maintenance Team - 1 (Ramesh Maurya)';

    INSERT INTO dbo.DepartmentDomainMaster (DepartmentId, DomainName, Keywords, DefaultRoles, Priority, IsActive)
    SELECT d.DeptID, N'Sales & Marketing',
           N'["sales","marketing","business development","b2b","b2c","digital marketing","seo","sem","lead generation","account management","branding","campaigns","client relationship"]',
           N'["Sales Executive","Business Development Manager","Digital Marketing Specialist","Account Executive"]',
           5, 1
    FROM dbo.OrgDepartmentMst d WHERE d.DeptName = N'Sales Team';

    INSERT INTO dbo.DepartmentDomainMaster (DepartmentId, DomainName, Keywords, DefaultRoles, Priority, IsActive)
    SELECT d.DeptID, N'Quality & EHS',
           N'["quality assurance","qa","qc","ehs","safety","environmental","iso","compliance","inspection","audit","safety officer","quality control"]',
           N'["Quality Assurance Engineer","EHS Specialist","Quality Control Inspector"]',
           6, 1
    FROM dbo.OrgDepartmentMst d WHERE d.DeptName = N'EHS Team';

    INSERT INTO dbo.DepartmentDomainMaster (DepartmentId, DomainName, Keywords, DefaultRoles, Priority, IsActive)
    SELECT d.DeptID, N'Supply Chain & Operations',
           N'["supply chain","logistics","procurement","inventory","warehouse","store keeper","purchase","vendor","distribution","operations manager"]',
           N'["Supply Chain Executive","Logistics Coordinator","Procurement Officer","Operations Manager"]',
           7, 1
    FROM dbo.OrgDepartmentMst d WHERE d.DeptName = N'Procurement Team';

    INSERT INTO dbo.DepartmentDomainMaster (DepartmentId, DomainName, Keywords, DefaultRoles, Priority, IsActive)
    VALUES (NULL, N'Healthcare & Clinical',
           N'["clinical","nurse","nursing","doctor","physician","patient","medical","hospital","pharma","pharmacist","laboratory"]',
           N'["Staff Nurse","Medical Officer","Clinical Specialist","Pharmacist"]',
           8, 1);
END
GO
