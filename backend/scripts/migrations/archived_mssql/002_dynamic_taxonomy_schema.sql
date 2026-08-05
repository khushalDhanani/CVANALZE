-- Migration: 002_dynamic_taxonomy_schema.sql
-- Description: Creates dynamic taxonomy master tables and family compatibility matrix in cvai schema.

IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'cvai')
BEGIN
    EXEC('CREATE SCHEMA cvai');
END
GO

-- 1. cvai.domains (Domain Master Table)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.domains'))
BEGIN
    CREATE TABLE cvai.domains (
        domain_id INT IDENTITY(1,1) PRIMARY KEY,
        domain_code VARCHAR(50) NOT NULL UNIQUE,
        domain_name NVARCHAR(255) NOT NULL,
        description NVARCHAR(500),
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
END
GO

-- 2. cvai.job_families (Job Family Master Table)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.job_families'))
BEGIN
    CREATE TABLE cvai.job_families (
        family_id INT IDENTITY(1,1) PRIMARY KEY,
        domain_id INT NOT NULL FOREIGN KEY REFERENCES cvai.domains(domain_id) ON DELETE CASCADE,
        family_code VARCHAR(50) NOT NULL UNIQUE,
        family_name NVARCHAR(255) NOT NULL,
        description NVARCHAR(500),
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
END
GO

-- 3. cvai.designations (Designation Master Table)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.designations'))
BEGIN
    CREATE TABLE cvai.designations (
        designation_id INT IDENTITY(1,1) PRIMARY KEY,
        family_id INT NOT NULL FOREIGN KEY REFERENCES cvai.job_families(family_id) ON DELETE CASCADE,
        designation_code VARCHAR(100) NOT NULL UNIQUE,
        designation_name NVARCHAR(255) NOT NULL,
        seniority_level VARCHAR(50),
        content_hash VARCHAR(64),
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
END
GO

-- 4. cvai.designation_synonyms (Designation Synonyms / Aliases Table)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.designation_synonyms'))
BEGIN
    CREATE TABLE cvai.designation_synonyms (
        synonym_id INT IDENTITY(1,1) PRIMARY KEY,
        designation_id INT NOT NULL FOREIGN KEY REFERENCES cvai.designations(designation_id) ON DELETE CASCADE,
        synonym_text NVARCHAR(255) NOT NULL,
        is_canonical BIT DEFAULT 0,
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IX_designation_synonyms_text ON cvai.designation_synonyms(synonym_text);
END
GO

-- 5. cvai.skills (Skills Master Table)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.skills'))
BEGIN
    CREATE TABLE cvai.skills (
        skill_id INT IDENTITY(1,1) PRIMARY KEY,
        domain_id INT NULL FOREIGN KEY REFERENCES cvai.domains(domain_id),
        skill_name NVARCHAR(255) NOT NULL UNIQUE,
        category VARCHAR(100) DEFAULT 'general',
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
END
GO

-- 6. cvai.designation_skills (Designation-to-Skill Mapping Table)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.designation_skills'))
BEGIN
    CREATE TABLE cvai.designation_skills (
        designation_id INT NOT NULL FOREIGN KEY REFERENCES cvai.designations(designation_id) ON DELETE CASCADE,
        skill_id INT NOT NULL FOREIGN KEY REFERENCES cvai.skills(skill_id) ON DELETE CASCADE,
        is_mandatory BIT DEFAULT 0,
        importance_weight FLOAT DEFAULT 1.0,
        PRIMARY KEY (designation_id, skill_id)
    );
END
GO

-- 7. cvai.family_compatibilities (Family Compatibility Matrix Table)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.family_compatibilities'))
BEGIN
    CREATE TABLE cvai.family_compatibilities (
        source_family_id INT NOT NULL FOREIGN KEY REFERENCES cvai.job_families(family_id),
        target_family_id INT NOT NULL FOREIGN KEY REFERENCES cvai.job_families(family_id),
        compatibility_score FLOAT NOT NULL CHECK (compatibility_score >= 0.0 AND compatibility_score <= 1.0),
        is_allowed BIT DEFAULT 1,
        PRIMARY KEY (source_family_id, target_family_id)
    );
END
GO
