-- Migration: 002_dynamic_taxonomy_schema.sql (PostgreSQL)
-- Description: Creates dynamic taxonomy master tables and family compatibility matrix in cvai schema.

CREATE SCHEMA IF NOT EXISTS cvai;

-- 1. cvai.domains (Domain Master Table)
CREATE TABLE IF NOT EXISTS cvai.domains (
    domain_id SERIAL PRIMARY KEY,
    domain_code VARCHAR(50) NOT NULL UNIQUE,
    domain_name VARCHAR(255) NOT NULL,
    description VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. cvai.job_families (Job Family Master Table)
CREATE TABLE IF NOT EXISTS cvai.job_families (
    family_id SERIAL PRIMARY KEY,
    domain_id INT NOT NULL REFERENCES cvai.domains(domain_id) ON DELETE CASCADE,
    family_code VARCHAR(50) NOT NULL UNIQUE,
    family_name VARCHAR(255) NOT NULL,
    description VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. cvai.designations (Designation Master Table)
CREATE TABLE IF NOT EXISTS cvai.designations (
    designation_id SERIAL PRIMARY KEY,
    family_id INT NOT NULL REFERENCES cvai.job_families(family_id) ON DELETE CASCADE,
    designation_code VARCHAR(100) NOT NULL UNIQUE,
    designation_name VARCHAR(255) NOT NULL,
    seniority_level VARCHAR(50),
    content_hash VARCHAR(64),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. cvai.designation_synonyms (Designation Synonyms / Aliases Table)
CREATE TABLE IF NOT EXISTS cvai.designation_synonyms (
    synonym_id SERIAL PRIMARY KEY,
    designation_id INT NOT NULL REFERENCES cvai.designations(designation_id) ON DELETE CASCADE,
    synonym_text VARCHAR(255) NOT NULL,
    is_canonical BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS IX_designation_synonyms_text ON cvai.designation_synonyms(synonym_text);

-- 5. cvai.skills (Skills Master Table)
CREATE TABLE IF NOT EXISTS cvai.skills (
    skill_id SERIAL PRIMARY KEY,
    domain_id INT REFERENCES cvai.domains(domain_id),
    skill_name VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100) DEFAULT 'general',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. cvai.designation_skills (Designation-to-Skill Mapping Table)
CREATE TABLE IF NOT EXISTS cvai.designation_skills (
    designation_id INT NOT NULL REFERENCES cvai.designations(designation_id) ON DELETE CASCADE,
    skill_id INT NOT NULL REFERENCES cvai.skills(skill_id) ON DELETE CASCADE,
    is_mandatory BOOLEAN DEFAULT FALSE,
    importance_weight DOUBLE PRECISION DEFAULT 1.0,
    PRIMARY KEY (designation_id, skill_id)
);

-- 7. cvai.family_compatibilities (Family Compatibility Matrix Table)
CREATE TABLE IF NOT EXISTS cvai.family_compatibilities (
    source_family_id INT NOT NULL REFERENCES cvai.job_families(family_id),
    target_family_id INT NOT NULL REFERENCES cvai.job_families(family_id),
    compatibility_score DOUBLE PRECISION NOT NULL CHECK (compatibility_score >= 0.0 AND compatibility_score <= 1.0),
    is_allowed BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (source_family_id, target_family_id)
);
