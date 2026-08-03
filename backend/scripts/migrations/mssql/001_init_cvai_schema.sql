-- Migration: 001_init_cvai_schema.sql
-- Description: Creates the cvai schema and tables following exact design principles.

IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'cvai')
BEGIN
    EXEC('CREATE SCHEMA cvai');
END
GO

-- 1. cv_documents (System of Record for File Parsing)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.cv_documents'))
BEGIN
    CREATE TABLE cvai.cv_documents (
        id VARCHAR(255) PRIMARY KEY,
        tenant_id VARCHAR(50),
        cv_hash VARCHAR(255) UNIQUE NOT NULL,
        filename NVARCHAR(500),
        content_type VARCHAR(100),
        page_count INT,
        is_scanned BIT,
        ocr_applied BIT,
        parser_used VARCHAR(100),
        parser_version VARCHAR(50),
        schema_version VARCHAR(50),
        parsed_at DATETIME2,
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME2 DEFAULT CURRENT_TIMESTAMP,
        text NVARCHAR(MAX),
        markdown NVARCHAR(MAX),
        structured_doc NVARCHAR(MAX) CHECK (structured_doc IS NULL OR ISJSON(structured_doc) = 1),
        quality_metrics NVARCHAR(MAX) CHECK (quality_metrics IS NULL OR ISJSON(quality_metrics) = 1),
        stage_metrics NVARCHAR(MAX) CHECK (stage_metrics IS NULL OR ISJSON(stage_metrics) = 1)
    );
END
GO

-- 2. candidates (Extraction vs. HR Corrections)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.candidates'))
BEGIN
    CREATE TABLE cvai.candidates (
        id VARCHAR(255) PRIMARY KEY,
        tenant_id VARCHAR(50),
        cv_document_id VARCHAR(255) FOREIGN KEY REFERENCES cvai.cv_documents(id) ON DELETE CASCADE,
        raw_skills_json NVARCHAR(MAX) CHECK (raw_skills_json IS NULL OR ISJSON(raw_skills_json) = 1),
        raw_education_json NVARCHAR(MAX) CHECK (raw_education_json IS NULL OR ISJSON(raw_education_json) = 1),
        raw_experience_json NVARCHAR(MAX) CHECK (raw_experience_json IS NULL OR ISJSON(raw_experience_json) = 1),
        raw_profile_json NVARCHAR(MAX) CHECK (raw_profile_json IS NULL OR ISJSON(raw_profile_json) = 1),
        hr_verified_data_json NVARCHAR(MAX) CHECK (hr_verified_data_json IS NULL OR ISJSON(hr_verified_data_json) = 1),
        schema_version VARCHAR(50),
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
END
GO

-- 3. match_results (Snapshots & Version Tracing)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.match_results'))
BEGIN
    CREATE TABLE cvai.match_results (
        id VARCHAR(255) PRIMARY KEY,
        tenant_id VARCHAR(50),
        candidate_id VARCHAR(255) FOREIGN KEY REFERENCES cvai.candidates(id) ON DELETE CASCADE,
        vacancy_id VARCHAR(255),
        vacancy_title NVARCHAR(500),
        department_name NVARCHAR(255),
        scoring_engine_version VARCHAR(50),
        rule_config_version VARCHAR(50),
        embedding_model_version VARCHAR(50),
        overall_score FLOAT,
        component_scores_json NVARCHAR(MAX) CHECK (component_scores_json IS NULL OR ISJSON(component_scores_json) = 1),
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
END
GO

-- 4. match_results_history (Append Only)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.match_results_history'))
BEGIN
    CREATE TABLE cvai.match_results_history (
        id BIGINT IDENTITY(1,1) PRIMARY KEY,
        tenant_id VARCHAR(50),
        match_result_id VARCHAR(255) FOREIGN KEY REFERENCES cvai.match_results(id) ON DELETE CASCADE,
        changed_by VARCHAR(255),
        previous_score FLOAT,
        new_score FLOAT,
        delta_json NVARCHAR(MAX) CHECK (delta_json IS NULL OR ISJSON(delta_json) = 1),
        scoring_engine_version VARCHAR(50),
        rule_config_version VARCHAR(50),
        created_at DATETIME2 DEFAULT CURRENT_TIMESTAMP
    );
END
GO
