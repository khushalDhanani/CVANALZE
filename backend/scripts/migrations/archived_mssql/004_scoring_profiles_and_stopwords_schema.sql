-- Migration: 004_scoring_profiles_and_stopwords_schema.sql
-- Description: Creates dynamic stop words and tenant scoring profile master tables in cvai schema.

IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'cvai')
BEGIN
    EXEC('CREATE SCHEMA cvai');
END
GO

-- 1. cvai.stop_words (Domain & Language Specific Stop Words)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.stop_words'))
BEGIN
    CREATE TABLE cvai.stop_words (
        stopword_id INT IDENTITY(1,1) PRIMARY KEY,
        word NVARCHAR(100) NOT NULL UNIQUE,
        category VARCHAR(100) DEFAULT 'prefilter', -- e.g., prefilter, search, general
        language VARCHAR(10) DEFAULT 'en',
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IX_stop_words_word ON cvai.stop_words(word);
END
GO

-- 2. cvai.scoring_profiles (Dynamic Scoring Profiles & Weight Overrides per Industry/Tenant)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.scoring_profiles'))
BEGIN
    CREATE TABLE cvai.scoring_profiles (
        profile_id INT IDENTITY(1,1) PRIMARY KEY,
        profile_code VARCHAR(50) NOT NULL UNIQUE,
        profile_name NVARCHAR(255) NOT NULL,
        description NVARCHAR(500),
        lexical_weights_json NVARCHAR(MAX) CHECK (lexical_weights_json IS NULL OR ISJSON(lexical_weights_json) = 1),
        component_weights_json NVARCHAR(MAX) CHECK (component_weights_json IS NULL OR ISJSON(component_weights_json) = 1),
        penalties_json NVARCHAR(MAX) CHECK (penalties_json IS NULL OR ISJSON(penalties_json) = 1),
        thresholds_json NVARCHAR(MAX) CHECK (thresholds_json IS NULL OR ISJSON(thresholds_json) = 1),
        is_default BIT DEFAULT 0,
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
END
GO
