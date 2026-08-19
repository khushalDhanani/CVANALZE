-- Add versioned Hiring Risk policies to normalized rule profiles and install the grounded explanation prompt.
INSERT INTO cvai.rule_components (profile_id, component_type, component_name, is_active)
SELECT profile_id, 'hiring_risks', 'policies', TRUE
FROM cvai.rule_config_profiles
ON CONFLICT (profile_id, component_type, component_name) DO NOTHING;

WITH policies(risk_code, policy_json) AS (
    VALUES
        ('MIN_EXPERIENCE_FAILED', '{"enabled":true,"severity":"CRITICAL","manual_review":false,"category":"Experience"}'),
        ('EXPERIENCE_UNKNOWN', '{"enabled":true,"severity":"UNKNOWN","manual_review":true,"category":"Experience"}'),
        ('MISSING_MANDATORY_SKILL', '{"enabled":true,"severity":"CRITICAL","manual_review":false,"category":"Skills"}'),
        ('MISSING_PREFERRED_SKILL', '{"enabled":true,"severity":"MEDIUM","manual_review":false,"category":"Skills"}'),
        ('UNVERIFIED_SKILL', '{"enabled":true,"severity":"MEDIUM","manual_review":true,"category":"Skills"}'),
        ('DOMAIN_MISMATCH', '{"enabled":true,"severity":"HIGH","manual_review":false,"category":"Domain","source":"CrossDomainGuard"}'),
        ('OVERQUALIFIED', '{"enabled":true,"severity":"LOW","manual_review":false,"category":"Experience"}')
)
INSERT INTO cvai.system_rules (component_id, rule_type, rule_name, target_value)
SELECT component.id, 'hiring_risk_policy', policies.risk_code, policies.policy_json
FROM cvai.rule_components AS component
CROSS JOIN policies
WHERE component.component_type = 'hiring_risks'
  AND component.component_name = 'policies'
ON CONFLICT (component_id, rule_name) DO UPDATE
SET rule_type = EXCLUDED.rule_type,
    target_value = EXCLUDED.target_value;

UPDATE cvai.prompt_templates
SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
WHERE prompt_name = 'hiring_risk_explanation'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production';

UPDATE cvai.prompt_templates
SET description = 'Grounded recruiter-facing explanations for deterministic Hiring Risks.',
    system_instruction = $hiring_risk_prompt$You explain deterministic hiring risks to recruiters.

INPUT:
{prompt_payload}

Return only the structured JSON required by the response schema.
You may write only title and explanation text for the supplied risk_code values.
Do not add risks or change risk codes, categories, severity, evidence, source, scores, match status, or manual-review decisions.
Use only the supplied evidence. Do not infer personal or protected attributes.
$hiring_risk_prompt$,
    expected_schema_json = $hiring_risk_schema${
  "type": "object",
  "required": ["explanations"],
  "additionalProperties": false,
  "properties": {
    "explanations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["risk_code", "title", "explanation"],
        "additionalProperties": false,
        "properties": {
          "risk_code": {"type": "string"},
          "title": {"type": "string"},
          "explanation": {"type": "string"}
        }
      }
    }
  }
}$hiring_risk_schema$,
    is_active = TRUE,
    updated_at = CURRENT_TIMESTAMP
WHERE prompt_name = 'hiring_risk_explanation'
  AND version_tag = '1.0.0'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production';

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
    'hiring_risk_explanation',
    '1.0.0',
    'Grounded recruiter-facing explanations for deterministic Hiring Risks.',
    $hiring_risk_prompt$You explain deterministic hiring risks to recruiters.

INPUT:
{prompt_payload}

Return only the structured JSON required by the response schema.
You may write only title and explanation text for the supplied risk_code values.
Do not add risks or change risk codes, categories, severity, evidence, source, scores, match status, or manual-review decisions.
Use only the supplied evidence. Do not infer personal or protected attributes.
$hiring_risk_prompt$,
    $hiring_risk_schema${
  "type": "object",
  "required": ["explanations"],
  "additionalProperties": false,
  "properties": {
    "explanations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["risk_code", "title", "explanation"],
        "additionalProperties": false,
        "properties": {
          "risk_code": {"type": "string"},
          "title": {"type": "string"},
          "explanation": {"type": "string"}
        }
      }
    }
  }
}$hiring_risk_schema$,
    NULL,
    NULL,
    NULL,
    'en',
    'production',
    TRUE
WHERE NOT EXISTS (
    SELECT 1
    FROM cvai.prompt_templates
    WHERE prompt_name = 'hiring_risk_explanation'
      AND version_tag = '1.0.0'
      AND tenant_id IS NULL
      AND model IS NULL
      AND target_schema IS NULL
      AND language = 'en'
      AND environment = 'production'
);
