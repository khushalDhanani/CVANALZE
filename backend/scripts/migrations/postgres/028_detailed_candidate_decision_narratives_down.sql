UPDATE cvai.prompt_templates
SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
WHERE prompt_name = 'optimized_match'
  AND version_tag = '3.8'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production';

UPDATE cvai.prompt_templates
SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
WHERE prompt_name = 'optimized_match'
  AND version_tag = '3.7'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production'
  AND prompt_id = (
      SELECT MAX(prompt_id)
      FROM cvai.prompt_templates
      WHERE prompt_name = 'optimized_match'
        AND version_tag = '3.7'
        AND tenant_id IS NULL
        AND model IS NULL
        AND target_schema IS NULL
        AND language = 'en'
        AND environment = 'production'
  );

DELETE FROM cvai.prompt_templates
WHERE prompt_name = 'optimized_match'
  AND version_tag = '3.8'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production';
