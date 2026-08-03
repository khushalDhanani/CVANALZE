-- Migration: 003_geo_and_headers_schema.sql
-- Description: Creates dynamic location gazetteers, section headings, and name denylist tables in cvai schema.

IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'cvai')
BEGIN
    EXEC('CREATE SCHEMA cvai');
END
GO

-- 1. cvai.geo_locations (Global Dynamic Location Gazetteer)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.geo_locations'))
BEGIN
    CREATE TABLE cvai.geo_locations (
        location_id INT IDENTITY(1,1) PRIMARY KEY,
        city_name NVARCHAR(255) NOT NULL,
        state_name NVARCHAR(255),
        country_name NVARCHAR(255) DEFAULT 'Global',
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IX_geo_locations_city ON cvai.geo_locations(city_name);
END
GO

-- 2. cvai.section_headings (Multilingual Section Heading Master)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.section_headings'))
BEGIN
    CREATE TABLE cvai.section_headings (
        heading_id INT IDENTITY(1,1) PRIMARY KEY,
        heading_text NVARCHAR(255) NOT NULL UNIQUE,
        category VARCHAR(100) DEFAULT 'general', -- e.g., experience, education, skills, contact
        language VARCHAR(10) DEFAULT 'en',
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IX_section_headings_text ON cvai.section_headings(heading_text);
END
GO

-- 3. cvai.name_denylists (Dynamic Name Extraction Filter Words)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.name_denylists'))
BEGIN
    CREATE TABLE cvai.name_denylists (
        denylist_id INT IDENTITY(1,1) PRIMARY KEY,
        word NVARCHAR(255) NOT NULL UNIQUE,
        category VARCHAR(100) DEFAULT 'job_title', -- e.g., job_title, header, generic
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IX_name_denylists_word ON cvai.name_denylists(word);
END
GO
