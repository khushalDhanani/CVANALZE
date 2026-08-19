DELETE FROM cvai.prompt_templates
WHERE prompt_name = 'optimized_match'
  AND version_tag = '3.6'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production';

UPDATE cvai.prompt_templates
SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
WHERE prompt_name = 'optimized_match'
  AND version_tag = '3.5'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production'
  AND prompt_id = (
      SELECT MAX(prompt_id)
      FROM cvai.prompt_templates
      WHERE prompt_name = 'optimized_match'
        AND version_tag = '3.5'
        AND tenant_id IS NULL
        AND model IS NULL
        AND target_schema IS NULL
        AND language = 'en'
        AND environment = 'production'
  );

UPDATE cvai.prompt_templates
SET system_instruction = CASE prompt_name
        WHEN 'profile_extraction' THEN '/no_think' || E'\n' || system_instruction
        ELSE '/think' || E'\n' || system_instruction
    END,
    updated_at = CURRENT_TIMESTAMP
WHERE prompt_name IN ('dynamic_mapping', 'match_analysis', 'profile_extraction')
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND system_instruction !~ E'^/(no_)?think(\\r?\\n|$)';
