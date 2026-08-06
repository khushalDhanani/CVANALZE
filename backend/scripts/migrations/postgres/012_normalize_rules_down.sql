-- Down migration

ALTER TABLE cvai.rule_components DROP CONSTRAINT IF EXISTS uq_rule_component_profile;
ALTER TABLE cvai.system_rules DROP CONSTRAINT IF EXISTS uq_system_rule_component;
ALTER TABLE cvai.rule_thresholds DROP CONSTRAINT IF EXISTS uq_rule_threshold_component;
ALTER TABLE cvai.rule_penalties DROP CONSTRAINT IF EXISTS uq_rule_penalty_component;
ALTER TABLE cvai.rule_weights DROP CONSTRAINT IF EXISTS uq_rule_weight_component;

ALTER TABLE cvai.rule_conditions ADD COLUMN keywords_json TEXT;

DROP TABLE IF EXISTS cvai.rule_condition_values;
