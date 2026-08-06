-- Migration Rollback: 008_normalized_configuration_schema_down.sql
-- Description: Reverts normalized configuration tables and restores legacy JSON columns.

DROP TABLE IF EXISTS cvai.rule_weights CASCADE;
DROP TABLE IF EXISTS cvai.rule_penalties CASCADE;
DROP TABLE IF EXISTS cvai.rule_thresholds CASCADE;
DROP TABLE IF EXISTS cvai.rule_condition_values CASCADE;
DROP TABLE IF EXISTS cvai.rule_conditions CASCADE;
DROP TABLE IF EXISTS cvai.system_rules CASCADE;
DROP TABLE IF EXISTS cvai.rule_components CASCADE;
DROP TABLE IF EXISTS cvai.rule_validation_tests CASCADE;

-- We don't drop rule_config_profiles completely if we just want to revert to the JSON structure.
ALTER TABLE cvai.rule_config_profiles ADD COLUMN IF NOT EXISTS global_confidence_tiers_json TEXT;
ALTER TABLE cvai.rule_config_profiles ADD COLUMN IF NOT EXISTS fields_config_json TEXT;
ALTER TABLE cvai.rule_config_profiles ADD COLUMN IF NOT EXISTS scoring_rules_json TEXT;

ALTER TABLE cvai.rule_config_profiles DROP CONSTRAINT IF EXISTS uq_rule_config_tenant_version;
