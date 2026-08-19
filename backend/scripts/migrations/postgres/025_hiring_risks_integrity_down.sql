DELETE FROM cvai.prompt_templates
WHERE prompt_name = 'hiring_risk_explanation'
  AND version_tag = '1.0.0'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production';

DELETE FROM cvai.rule_components
WHERE component_type = 'hiring_risks'
  AND component_name = 'policies';
