DROP INDEX IF EXISTS cvai.uq_rule_config_tenant_active;
DROP INDEX IF EXISTS cvai.uq_rule_config_global_active;
DROP INDEX IF EXISTS cvai.uq_rule_config_global_version;

ALTER TABLE cvai.rule_conditions
    DROP COLUMN IF EXISTS branch_index;
