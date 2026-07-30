-- Migration: 001_init_cvai_schema.sql
-- Description: Creates the cvai schema and tables for CV documents and candidate profiles.

IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'cvai')
BEGIN
    EXEC('CREATE SCHEMA cvai');
END
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.cv_documents'))
BEGIN
    CREATE TABLE cvai.cv_documents (
        id VARCHAR(255) PRIMARY KEY,
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
        created_at DATETIME2,
        updated_at DATETIME2,
        text NVARCHAR(MAX),
        markdown NVARCHAR(MAX),
        structured_doc NVARCHAR(MAX),
        quality_metrics NVARCHAR(MAX),
        stage_metrics NVARCHAR(MAX)
    );
END
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE object_id = OBJECT_ID('cvai.candidates'))
BEGIN
    CREATE TABLE cvai.candidates (
        id VARCHAR(255) PRIMARY KEY,
        cv_document_id VARCHAR(255),
        dynamic_profile NVARCHAR(MAX),
        resume_json NVARCHAR(MAX),
        match_analysis NVARCHAR(MAX),
        created_at DATETIME2,
        CONSTRAINT FK_candidates_cv_document FOREIGN KEY (cv_document_id) REFERENCES cvai.cv_documents(id) ON DELETE CASCADE
    );
END
GO
