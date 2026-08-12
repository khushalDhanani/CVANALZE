-- Preserve taxonomy branch semantics and enforce one deterministic active profile per scope.
ALTER TABLE cvai.rule_conditions
    ADD COLUMN IF NOT EXISTS branch_index INTEGER NOT NULL DEFAULT 0;

CREATE UNIQUE INDEX IF NOT EXISTS uq_rule_config_global_version
    ON cvai.rule_config_profiles (version_tag)
    WHERE tenant_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_rule_config_global_active
    ON cvai.rule_config_profiles (is_active)
    WHERE tenant_id IS NULL AND is_active IS TRUE;

CREATE UNIQUE INDEX IF NOT EXISTS uq_rule_config_tenant_active
    ON cvai.rule_config_profiles (tenant_id)
    WHERE tenant_id IS NOT NULL AND is_active IS TRUE;
