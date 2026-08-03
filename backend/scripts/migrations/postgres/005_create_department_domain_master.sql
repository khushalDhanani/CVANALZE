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

-- Seed initial domain master rows if table is empty
INSERT INTO "DepartmentDomainMaster" ("DepartmentId", "DomainName", "Keywords", "DefaultRoles", "Priority", "IsActive")
SELECT NULL, 'Information Technology & Software',
       '["developer","engineer","software","flutter","react","frontend","backend","full stack","fullstack","python","java","javascript","typescript","dart","c#","dotnet","sql","api","mobile","ios","android","devops","cloud","aws","azure","docker","kubernetes","database","ui/ux","web","coding","code"]'::jsonb,
       '["Software Developer","Full Stack Engineer","Frontend/Mobile Engineer","Backend Developer"]'::jsonb,
       1, TRUE
WHERE NOT EXISTS (SELECT 1 FROM "DepartmentDomainMaster" WHERE "DomainName" = 'Information Technology & Software');

INSERT INTO "DepartmentDomainMaster" ("DepartmentId", "DomainName", "Keywords", "DefaultRoles", "Priority", "IsActive")
SELECT NULL, 'Finance & Accounting',
       '["finance","financial","accounting","accountant","audit","tax","ca","cpa","cfa","tally","ledger","payroll","budgeting","forecasting","treasury","billing","valuation"]'::jsonb,
       '["Financial Analyst","Accountant","Finance Manager","Audit Specialist"]'::jsonb,
       2, TRUE
WHERE NOT EXISTS (SELECT 1 FROM "DepartmentDomainMaster" WHERE "DomainName" = 'Finance & Accounting');

INSERT INTO "DepartmentDomainMaster" ("DepartmentId", "DomainName", "Keywords", "DefaultRoles", "Priority", "IsActive")
SELECT NULL, 'Human Resources',
       '["hr","human resources","recruitment","recruiter","talent acquisition","onboarding","employee relations","performance management","hrbp","payroll management","people operations"]'::jsonb,
       '["HR Executive","Talent Acquisition Specialist","HR Generalist","Recruiter"]'::jsonb,
       3, TRUE
WHERE NOT EXISTS (SELECT 1 FROM "DepartmentDomainMaster" WHERE "DomainName" = 'Human Resources');

INSERT INTO "DepartmentDomainMaster" ("DepartmentId", "DomainName", "Keywords", "DefaultRoles", "Priority", "IsActive")
SELECT NULL, 'Plant & Maintenance Engineering',
       '["plant","maintenance","mechanical","electrical","utility","instrumentation","boiler","hvac","plc","scada","equipment","preventive maintenance","technician","machinery","fabrication"]'::jsonb,
       '["Plant Maintenance Engineer","Maintenance Technician","Mechanical Engineer","Plant Assistant"]'::jsonb,
       4, TRUE
WHERE NOT EXISTS (SELECT 1 FROM "DepartmentDomainMaster" WHERE "DomainName" = 'Plant & Maintenance Engineering');

INSERT INTO "DepartmentDomainMaster" ("DepartmentId", "DomainName", "Keywords", "DefaultRoles", "Priority", "IsActive")
SELECT NULL, 'Sales & Marketing',
       '["sales","marketing","business development","b2b","b2c","digital marketing","seo","sem","lead generation","account management","branding","campaigns","client relationship"]'::jsonb,
       '["Sales Executive","Business Development Manager","Digital Marketing Specialist","Account Executive"]'::jsonb,
       5, TRUE
WHERE NOT EXISTS (SELECT 1 FROM "DepartmentDomainMaster" WHERE "DomainName" = 'Sales & Marketing');

INSERT INTO "DepartmentDomainMaster" ("DepartmentId", "DomainName", "Keywords", "DefaultRoles", "Priority", "IsActive")
SELECT NULL, 'Quality & EHS',
       '["quality assurance","qa","qc","ehs","safety","environmental","iso","compliance","inspection","audit","safety officer","quality control"]'::jsonb,
       '["Quality Assurance Engineer","EHS Specialist","Quality Control Inspector"]'::jsonb,
       6, TRUE
WHERE NOT EXISTS (SELECT 1 FROM "DepartmentDomainMaster" WHERE "DomainName" = 'Quality & EHS');

INSERT INTO "DepartmentDomainMaster" ("DepartmentId", "DomainName", "Keywords", "DefaultRoles", "Priority", "IsActive")
SELECT NULL, 'Supply Chain & Operations',
       '["supply chain","logistics","procurement","inventory","warehouse","store keeper","purchase","vendor","distribution","operations manager"]'::jsonb,
       '["Supply Chain Executive","Logistics Coordinator","Procurement Officer","Operations Manager"]'::jsonb,
       7, TRUE
WHERE NOT EXISTS (SELECT 1 FROM "DepartmentDomainMaster" WHERE "DomainName" = 'Supply Chain & Operations');

INSERT INTO "DepartmentDomainMaster" ("DepartmentId", "DomainName", "Keywords", "DefaultRoles", "Priority", "IsActive")
SELECT NULL, 'Healthcare & Clinical',
       '["clinical","nurse","nursing","doctor","physician","patient","medical","hospital","pharma","pharmacist","laboratory"]'::jsonb,
       '["Staff Nurse","Medical Officer","Clinical Specialist","Pharmacist"]'::jsonb,
       8, TRUE
WHERE NOT EXISTS (SELECT 1 FROM "DepartmentDomainMaster" WHERE "DomainName" = 'Healthcare & Clinical');
