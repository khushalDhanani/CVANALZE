-- Migration: 003_geo_and_headers_schema.sql (PostgreSQL)
-- Description: Creates dynamic location gazetteers, section headings, and name denylist tables in cvai schema.

CREATE SCHEMA IF NOT EXISTS cvai;

-- 1. cvai.geo_locations (Global Dynamic Location Gazetteer)
CREATE TABLE IF NOT EXISTS cvai.geo_locations (
    location_id SERIAL PRIMARY KEY,
    city_name VARCHAR(255) NOT NULL,
    state_name VARCHAR(255),
    country_name VARCHAR(255) DEFAULT 'Global',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS IX_geo_locations_city ON cvai.geo_locations(city_name);

-- 2. cvai.section_headings (Multilingual Section Heading Master)
CREATE TABLE IF NOT EXISTS cvai.section_headings (
    heading_id SERIAL PRIMARY KEY,
    heading_text VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100) DEFAULT 'general',
    language VARCHAR(10) DEFAULT 'en',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS IX_section_headings_text ON cvai.section_headings(heading_text);

-- 3. cvai.name_denylists (Dynamic Name Extraction Filter Words)
CREATE TABLE IF NOT EXISTS cvai.name_denylists (
    denylist_id SERIAL PRIMARY KEY,
    word VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100) DEFAULT 'job_title',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS IX_name_denylists_word ON cvai.name_denylists(word);
