-- Up migration for replacing keywords_json with rule_condition_values and adding uniqueness constraints

CREATE TABLE cvai.rule_condition_values (
    id SERIAL PRIMARY KEY,
    condition_id INTEGER NOT NULL REFERENCES cvai.rule_conditions(id) ON DELETE CASCADE,
    value VARCHAR(500) NOT NULL
);

-- Note: In a production scenario with live data, we would write a complex data migration here
-- to extract JSON array elements into the rule_condition_values table.
-- Since this is an initial architecture change before data goes live, we can just drop the column.
ALTER TABLE cvai.rule_conditions DROP COLUMN keywords_json;

-- Add Uniqueness Constraints
ALTER TABLE cvai.rule_components ADD CONSTRAINT uq_rule_component_profile UNIQUE (profile_id, component_type, component_name);
ALTER TABLE cvai.system_rules ADD CONSTRAINT uq_system_rule_component UNIQUE (component_id, rule_name);
ALTER TABLE cvai.rule_thresholds ADD CONSTRAINT uq_rule_threshold_component UNIQUE (component_id, threshold_key);
ALTER TABLE cvai.rule_penalties ADD CONSTRAINT uq_rule_penalty_component UNIQUE (component_id, penalty_key);
ALTER TABLE cvai.rule_weights ADD CONSTRAINT uq_rule_weight_component UNIQUE (component_id, weight_key);
