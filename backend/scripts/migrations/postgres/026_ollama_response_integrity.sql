-- Remove model-specific prompt directives and activate a cache-safe optimized prompt version.
UPDATE cvai.prompt_templates
SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
WHERE prompt_name = 'optimized_match'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production'
  AND is_active IS TRUE;

INSERT INTO cvai.prompt_templates (
    prompt_name,
    version_tag,
    description,
    system_instruction,
    expected_schema_json,
    tenant_id,
    model,
    target_schema,
    language,
    environment,
    is_active
)
SELECT
    prompt_name,
    '3.6',
    'Model-neutral evidence-grounded optimized CV matching prompt.',
    regexp_replace(system_instruction, E'^/(no_)?think(\\r?\\n|$)', ''),
    expected_schema_json,
    tenant_id,
    model,
    target_schema,
    language,
    environment,
    TRUE
FROM cvai.prompt_templates
WHERE prompt_name = 'optimized_match'
  AND version_tag = '3.5'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production'
ORDER BY prompt_id DESC
LIMIT 1;

UPDATE cvai.prompt_templates
SET system_instruction = regexp_replace(system_instruction, E'^/(no_)?think(\\r?\\n|$)', ''),
    updated_at = CURRENT_TIMESTAMP
WHERE prompt_name IN ('dynamic_mapping', 'match_analysis', 'profile_extraction')
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND system_instruction ~ E'^/(no_)?think(\\r?\\n|$)';
