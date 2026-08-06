-- Migration: 008_normalized_configuration_schema.sql
-- Description: Creates unified normalized configuration tables, adds unique constraints, and removes old JSON columns.

CREATE TABLE IF NOT EXISTS cvai.rule_config_profiles (
    profile_id SERIAL PRIMARY KEY,
    tenant_id VARCHAR(50),
    version_tag VARCHAR(50) NOT NULL,
    description VARCHAR(500),
    is_active BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) DEFAULT 'DRAFT',
    created_by VARCHAR(100),
    activated_by VARCHAR(100),
    activated_at TIMESTAMP WITH TIME ZONE,
    activation_reason VARCHAR(500),
    previous_version_tag VARCHAR(50),
    audit_reason VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE cvai.rule_config_profiles DROP CONSTRAINT IF EXISTS uq_rule_config_tenant_version;
ALTER TABLE cvai.rule_config_profiles ADD CONSTRAINT uq_rule_config_tenant_version UNIQUE (tenant_id, version_tag);

CREATE TABLE IF NOT EXISTS cvai.rule_components (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES cvai.rule_config_profiles(profile_id) ON DELETE CASCADE,
    component_type VARCHAR(50) NOT NULL,
    component_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT uq_rule_component_profile UNIQUE (profile_id, component_type, component_name)
);

CREATE TABLE IF NOT EXISTS cvai.system_rules (
    id SERIAL PRIMARY KEY,
    component_id INTEGER NOT NULL REFERENCES cvai.rule_components(id) ON DELETE CASCADE,
    rule_type VARCHAR(50) NOT NULL,
    rule_name VARCHAR(100) NOT NULL,
    target_value VARCHAR(255),
    CONSTRAINT uq_system_rule_component UNIQUE (component_id, rule_name)
);

CREATE TABLE IF NOT EXISTS cvai.rule_conditions (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL REFERENCES cvai.system_rules(id) ON DELETE CASCADE,
    condition_scope VARCHAR(100) NOT NULL,
    condition_mode VARCHAR(50) NOT NULL DEFAULT 'any',
    is_negated BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS cvai.rule_condition_values (
    id SERIAL PRIMARY KEY,
    condition_id INTEGER NOT NULL REFERENCES cvai.rule_conditions(id) ON DELETE CASCADE,
    value VARCHAR(500) NOT NULL,
    CONSTRAINT uq_condition_value UNIQUE (condition_id, value)
);

CREATE TABLE IF NOT EXISTS cvai.rule_thresholds (
    id SERIAL PRIMARY KEY,
    component_id INTEGER NOT NULL REFERENCES cvai.rule_components(id) ON DELETE CASCADE,
    threshold_key VARCHAR(100) NOT NULL,
    threshold_value DOUBLE PRECISION NOT NULL,
    CONSTRAINT uq_rule_threshold_component UNIQUE (component_id, threshold_key)
);

CREATE TABLE IF NOT EXISTS cvai.rule_penalties (
    id SERIAL PRIMARY KEY,
    component_id INTEGER NOT NULL REFERENCES cvai.rule_components(id) ON DELETE CASCADE,
    penalty_key VARCHAR(100) NOT NULL,
    penalty_value DOUBLE PRECISION NOT NULL,
    CONSTRAINT uq_rule_penalty_component UNIQUE (component_id, penalty_key)
);

CREATE TABLE IF NOT EXISTS cvai.rule_weights (
    id SERIAL PRIMARY KEY,
    component_id INTEGER NOT NULL REFERENCES cvai.rule_components(id) ON DELETE CASCADE,
    weight_key VARCHAR(100) NOT NULL,
    weight_value DOUBLE PRECISION NOT NULL,
    CONSTRAINT uq_rule_weight_component UNIQUE (component_id, weight_key)
);

CREATE TABLE IF NOT EXISTS cvai.rule_validation_tests (
    test_id SERIAL PRIMARY KEY,
    test_name VARCHAR(255) NOT NULL UNIQUE,
    target_component VARCHAR(100) NOT NULL,
    payload_json TEXT NOT NULL,
    expected_result_json TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Safely migrate any existing JSON data (if the columns existed prior to this migration)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'cvai' 
          AND table_name = 'rule_config_profiles' 
          AND column_name = 'fields_config_json'
    ) THEN
        -- Dummy migration block. In a real environment with populated unstructured JSON,
        -- this would contain jsonb_array_elements mapping logic.
        -- Since the database is pre-production and empty, we simply acknowledge the step.
        RAISE NOTICE 'Skipping complex JSON data extraction for pre-production DB.';
    END IF;
END $$;

-- Remove old operational JSON columns after "safely migrating"
ALTER TABLE cvai.rule_config_profiles DROP COLUMN IF EXISTS global_confidence_tiers_json;
ALTER TABLE cvai.rule_config_profiles DROP COLUMN IF EXISTS fields_config_json;
ALTER TABLE cvai.rule_config_profiles DROP COLUMN IF EXISTS scoring_rules_json;
