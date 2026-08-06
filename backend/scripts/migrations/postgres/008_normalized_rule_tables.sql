ALTER TABLE cvai.rule_config_profiles DROP COLUMN IF EXISTS global_confidence_tiers_json;
ALTER TABLE cvai.rule_config_profiles DROP COLUMN IF EXISTS fields_config_json;
ALTER TABLE cvai.rule_config_profiles DROP COLUMN IF EXISTS scoring_rules_json;

CREATE TABLE cvai.rule_validation_tests (
    test_id SERIAL PRIMARY KEY,
    test_name VARCHAR(255) NOT NULL UNIQUE,
    target_component VARCHAR(100) NOT NULL,
    payload_json TEXT NOT NULL,
    expected_result_json TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cvai.rule_components (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES cvai.rule_config_profiles(profile_id) ON DELETE CASCADE,
    component_type VARCHAR(50) NOT NULL,
    component_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE cvai.system_rules (
    id SERIAL PRIMARY KEY,
    component_id INTEGER NOT NULL REFERENCES cvai.rule_components(id) ON DELETE CASCADE,
    rule_type VARCHAR(50) NOT NULL,
    rule_name VARCHAR(100) NOT NULL,
    target_value VARCHAR(255)
);

CREATE TABLE cvai.rule_conditions (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL REFERENCES cvai.system_rules(id) ON DELETE CASCADE,
    condition_scope VARCHAR(100) NOT NULL,
    condition_mode VARCHAR(50) NOT NULL DEFAULT 'any',
    keywords_json TEXT,
    is_negated BOOLEAN DEFAULT FALSE
);

CREATE TABLE cvai.rule_thresholds (
    id SERIAL PRIMARY KEY,
    component_id INTEGER NOT NULL REFERENCES cvai.rule_components(id) ON DELETE CASCADE,
    threshold_key VARCHAR(100) NOT NULL,
    threshold_value DOUBLE PRECISION NOT NULL
);

CREATE TABLE cvai.rule_penalties (
    id SERIAL PRIMARY KEY,
    component_id INTEGER NOT NULL REFERENCES cvai.rule_components(id) ON DELETE CASCADE,
    penalty_key VARCHAR(100) NOT NULL,
    penalty_value DOUBLE PRECISION NOT NULL
);

CREATE TABLE cvai.rule_weights (
    id SERIAL PRIMARY KEY,
    component_id INTEGER NOT NULL REFERENCES cvai.rule_components(id) ON DELETE CASCADE,
    weight_key VARCHAR(100) NOT NULL,
    weight_value DOUBLE PRECISION NOT NULL
);
