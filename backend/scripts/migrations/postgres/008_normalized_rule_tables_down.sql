DROP TABLE IF EXISTS cvai.rule_weights CASCADE;
DROP TABLE IF EXISTS cvai.rule_penalties CASCADE;
DROP TABLE IF EXISTS cvai.rule_thresholds CASCADE;
DROP TABLE IF EXISTS cvai.rule_conditions CASCADE;
DROP TABLE IF EXISTS cvai.system_rules CASCADE;
DROP TABLE IF EXISTS cvai.rule_components CASCADE;
DROP TABLE IF EXISTS cvai.rule_validation_tests CASCADE;

ALTER TABLE cvai.rule_config_profiles ADD COLUMN global_confidence_tiers_json TEXT;
ALTER TABLE cvai.rule_config_profiles ADD COLUMN fields_config_json TEXT;
ALTER TABLE cvai.rule_config_profiles ADD COLUMN scoring_rules_json TEXT;
