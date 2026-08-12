DROP INDEX IF EXISTS cvai.uq_prompt_templates_active_scope;

DELETE FROM cvai.prompt_templates
WHERE prompt_name = 'optimized_match'
  AND version_tag = '3.5'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production';
