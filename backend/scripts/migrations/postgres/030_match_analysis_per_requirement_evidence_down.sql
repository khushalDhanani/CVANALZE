-- Rollback: deactivate match_analysis v1.2.0 and optimized_match v4.0; reactivate v1.1.0 and v3.9.
-- Does not delete rows (safe rollback preserving audit trail).
UPDATE cvai.prompt_templates
SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
WHERE ((prompt_name = 'match_analysis' AND version_tag = '1.2.0')
    OR (prompt_name = 'optimized_match' AND version_tag = '4.0'))
  AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
  AND language = 'en' AND environment = 'production';

UPDATE cvai.prompt_templates
SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
WHERE ((prompt_name = 'match_analysis' AND version_tag = '1.1.0')
    OR (prompt_name = 'optimized_match' AND version_tag = '3.9'))
  AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
  AND language = 'en' AND environment = 'production';
