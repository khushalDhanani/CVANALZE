-- Migration: 001_init_cvai_schema.sql (PostgreSQL)
-- Description: Creates the cvai schema and core tracking tables in PostgreSQL.

CREATE SCHEMA IF NOT EXISTS cvai;

-- 1. cv_documents (System of Record for File Parsing)
CREATE TABLE IF NOT EXISTS cvai.cv_documents (
    id VARCHAR(255) PRIMARY KEY,
    tenant_id VARCHAR(50),
    cv_hash VARCHAR(255) UNIQUE NOT NULL,
    filename VARCHAR(500),
    content_type VARCHAR(100),
    page_count INT,
    is_scanned BOOLEAN DEFAULT FALSE,
    ocr_applied BOOLEAN DEFAULT FALSE,
    parser_used VARCHAR(100),
    parser_version VARCHAR(50),
    schema_version VARCHAR(50),
    parsed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    text TEXT,
    markdown TEXT,
    structured_doc JSONB,
    quality_metrics JSONB,
    stage_metrics JSONB
);

-- 2. candidates (Extraction vs. HR Corrections)
CREATE TABLE IF NOT EXISTS cvai.candidates (
    id VARCHAR(255) PRIMARY KEY,
    tenant_id VARCHAR(50),
    cv_document_id VARCHAR(255) REFERENCES cvai.cv_documents(id) ON DELETE CASCADE,
    raw_skills_json JSONB,
    raw_education_json JSONB,
    raw_experience_json JSONB,
    raw_profile_json JSONB,
    hr_verified_data_json JSONB,
    schema_version VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. match_results (Snapshots & Version Tracing)
CREATE TABLE IF NOT EXISTS cvai.match_results (
    id VARCHAR(255) PRIMARY KEY,
    tenant_id VARCHAR(50),
    candidate_id VARCHAR(255) REFERENCES cvai.candidates(id) ON DELETE CASCADE,
    vacancy_id VARCHAR(255),
    vacancy_title VARCHAR(500),
    department_name VARCHAR(255),
    scoring_engine_version VARCHAR(50),
    rule_config_version VARCHAR(50),
    embedding_model_version VARCHAR(50),
    overall_score DOUBLE PRECISION,
    component_scores_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. match_results_history (Append Only)
CREATE TABLE IF NOT EXISTS cvai.match_results_history (
    id BIGSERIAL PRIMARY KEY,
    tenant_id VARCHAR(50),
    match_result_id VARCHAR(255) REFERENCES cvai.match_results(id) ON DELETE CASCADE,
    changed_by VARCHAR(255),
    previous_score DOUBLE PRECISION,
    new_score DOUBLE PRECISION,
    delta_json JSONB,
    scoring_engine_version VARCHAR(50),
    rule_config_version VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
