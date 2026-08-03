-- Migration: 004_scoring_profiles_and_stopwords_schema.sql (PostgreSQL)
-- Description: Creates dynamic stop words and tenant scoring profile master tables in cvai schema.

CREATE SCHEMA IF NOT EXISTS cvai;

-- 1. cvai.stop_words (Domain & Language Specific Stop Words)
CREATE TABLE IF NOT EXISTS cvai.stop_words (
    stopword_id SERIAL PRIMARY KEY,
    word VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(100) DEFAULT 'prefilter',
    language VARCHAR(10) DEFAULT 'en',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS IX_stop_words_word ON cvai.stop_words(word);

-- 2. cvai.scoring_profiles (Dynamic Scoring Profiles & Weight Overrides per Industry/Tenant)
CREATE TABLE IF NOT EXISTS cvai.scoring_profiles (
    profile_id SERIAL PRIMARY KEY,
    profile_code VARCHAR(50) NOT NULL UNIQUE,
    profile_name VARCHAR(255) NOT NULL,
    description VARCHAR(500),
    lexical_weights_json JSONB,
    component_weights_json JSONB,
    penalties_json JSONB,
    thresholds_json JSONB,
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
