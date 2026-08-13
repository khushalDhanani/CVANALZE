-- Version both CV/JD analysis prompts with grounded requirement-level assessments.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM cvai.prompt_templates
        WHERE prompt_name = 'optimized_match' AND version_tag = '3.8'
          AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
          AND language = 'en' AND environment = 'production'
    ) THEN
        RAISE EXCEPTION 'optimized_match prompt version 3.8 is required before installing version 3.9';
    END IF;
END $$;

INSERT INTO cvai.prompt_templates (
    prompt_name, version_tag, description, system_instruction, expected_schema_json,
    tenant_id, model, target_schema, language, environment, is_active
)
SELECT
    prompt_name,
    '3.9',
    'Evidence-grounded optimized CV matching with requirement-level rationale, confidence, and impact.',
    replace(
        replace(
            system_instruction,
            E'\nINSTRUCTIONS:',
            $requirement_rules$
REQUIREMENT ASSESSMENTS:
15. Return one requirement_assessments item for every supplied requirement_id and do not add requirements.
16. Copy requirement, category, mandatory, and jd_evidence from the supplied requirement. Mark mandatory only from the supplied flag.
17. cv_evidence must be an exact CV quote or fact for DIRECT, INFERRED, and PARTIAL.
    Use an empty string for MISSING or NOT_ASSESSABLE; never invent evidence.
18. match_type must be DIRECT, INFERRED, PARTIAL, MISSING, or NOT_ASSESSABLE. Explain the classification in rationale.
19. confidence is evidence certainty from 0.0 to 1.0, not a match score.
    impact is CRITICAL, HIGH, MEDIUM, or LOW and cannot alter deterministic scoring.
20. A missing mandatory requirement must have CRITICAL impact.

INSTRUCTIONS:$requirement_rules$
        ),
        $old_example$      "classified_requirements": [$old_example$,
        $new_example$      "requirement_assessments": [
        {{
          "requirement_id": "skill_1",
          "requirement": "Python",
          "category": "SKILL",
          "mandatory": true,
          "cv_evidence": "Built Python APIs using FastAPI",
          "jd_evidence": "Python",
          "rationale": "The resume directly demonstrates the required technology in delivered API work.",
          "match_type": "DIRECT",
          "confidence": 0.98,
          "impact": "LOW"
        }}
      ],
      "classified_requirements": [$new_example$
    ),
    $optimized_match_schema${
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "$id": "cvai://prompts/optimized_match/response-schema/v4",
      "type": "object",
      "required": ["candidate_profile", "active_vacancy_summary", "ai_career_summary", "matched_vacancies"],
      "properties": {
        "candidate_profile": {"type": "object"},
        "active_vacancy_summary": {"type": "string"},
        "ai_career_summary": {"type": "string"},
        "matched_vacancies": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["vacancy_id", "semantic_reason", "top_strength", "main_concern", "ai_match_explanation", "semantic_fit_score", "requirement_assessments"],
            "properties": {
              "vacancy_id": {"type": ["integer", "string"]},
              "semantic_reason": {"type": "string", "minLength": 1},
              "top_strength": {"type": "string", "minLength": 80, "maxLength": 1200},
              "main_concern": {"type": "string", "minLength": 80, "maxLength": 1200},
              "ai_match_explanation": {"type": "string", "minLength": 80, "maxLength": 1200},
              "semantic_fit_score": {"type": "number", "minimum": 0, "maximum": 100},
              "requirement_assessments": {
                "type": "array",
                "items": {
                  "type": "object",
                  "required": ["requirement_id", "requirement", "category", "mandatory", "cv_evidence", "jd_evidence", "rationale", "match_type", "confidence", "impact"],
                  "properties": {
                    "requirement_id": {"type": "string", "minLength": 1},
                    "requirement": {"type": "string", "minLength": 1},
                    "category": {"type": "string", "minLength": 1},
                    "mandatory": {"type": "boolean"},
                    "cv_evidence": {"type": "string"},
                    "jd_evidence": {"type": "string", "minLength": 1},
                    "rationale": {"type": "string", "minLength": 1},
                    "match_type": {"enum": ["DIRECT", "INFERRED", "PARTIAL", "MISSING", "NOT_ASSESSABLE"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "impact": {"enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]}
                  }
                }
              },
              "classified_requirements": {"type": "array"},
              "evidence_snippets": {"type": "object"}
            }
          }
        }
      }
    }$optimized_match_schema$,
    tenant_id, model, target_schema, language, environment, FALSE
FROM cvai.prompt_templates
WHERE prompt_name = 'optimized_match' AND version_tag = '3.8'
  AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
  AND language = 'en' AND environment = 'production'
  AND NOT EXISTS (
      SELECT 1 FROM cvai.prompt_templates existing
      WHERE existing.prompt_name = 'optimized_match' AND existing.version_tag = '3.9'
        AND existing.tenant_id IS NULL AND existing.model IS NULL AND existing.target_schema IS NULL
        AND existing.language = 'en' AND existing.environment = 'production'
  )
ORDER BY prompt_id DESC
LIMIT 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM cvai.prompt_templates
        WHERE prompt_name = 'optimized_match' AND version_tag = '3.9'
          AND strpos(system_instruction, 'REQUIREMENT ASSESSMENTS:') > 0
          AND strpos(system_instruction, '"requirement_assessments"') > 0
          AND strpos(expected_schema_json, 'response-schema/v4') > 0
    ) THEN
        RAISE EXCEPTION 'optimized_match prompt version 3.9 did not install the requirement assessment contract';
    END IF;
END $$;

INSERT INTO cvai.prompt_templates (
    prompt_name, version_tag, description, system_instruction, expected_schema_json,
    tenant_id, model, target_schema, language, environment, is_active
)
SELECT
    'match_analysis',
    '1.1.0',
    'Requirement-level CV and JD match analysis with grounded evidence, confidence, and impact.',
    $match_analysis_prompt${input_json}

Assess every supplied requirement separately. Use only exact facts from the CV and JD.
For DIRECT, INFERRED, or PARTIAL matches, cv_evidence must cite the explicit CV fact supporting the classification.
For MISSING or NOT_ASSESSABLE, use an empty cv_evidence string instead of inventing evidence.
Confidence is certainty in the evidence classification, not a match score. Impact is the recruiting consequence; a missing mandatory requirement is CRITICAL.
Return exactly one requirement_assessments item for every supplied requirement_id and do not add requirements.

Return only valid JSON matching the response schema, without markdown or extra commentary.$match_analysis_prompt$,
    $match_analysis_schema${
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "$id": "cvai://prompts/match_analysis/response-schema/v2",
      "type": "object",
      "required": ["skill_matches", "inferred_skills", "missing_critical", "semantic_reason", "requirement_assessments"],
      "properties": {
        "skill_matches": {"type": "array", "items": {"type": "string"}},
        "inferred_skills": {"type": "array", "items": {"type": "string"}},
        "missing_critical": {"type": "array", "items": {"type": "string"}},
        "semantic_reason": {"type": "string", "minLength": 1},
        "requirement_assessments": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["requirement_id", "requirement", "category", "mandatory", "cv_evidence", "jd_evidence", "rationale", "match_type", "confidence", "impact"],
            "properties": {
              "requirement_id": {"type": "string", "minLength": 1},
              "requirement": {"type": "string", "minLength": 1},
              "category": {"type": "string", "minLength": 1},
              "mandatory": {"type": "boolean"},
              "cv_evidence": {"type": "string"},
              "jd_evidence": {"type": "string", "minLength": 1},
              "rationale": {"type": "string", "minLength": 1},
              "match_type": {"enum": ["DIRECT", "INFERRED", "PARTIAL", "MISSING", "NOT_ASSESSABLE"]},
              "confidence": {"type": "number", "minimum": 0, "maximum": 1},
              "impact": {"enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]}
            }
          }
        }
      }
    }$match_analysis_schema$,
    NULL, NULL, NULL, 'en', 'production', FALSE
WHERE NOT EXISTS (
    SELECT 1 FROM cvai.prompt_templates
    WHERE prompt_name = 'match_analysis' AND version_tag = '1.1.0'
      AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
      AND language = 'en' AND environment = 'production'
);

UPDATE cvai.prompt_templates
SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
WHERE prompt_name IN ('optimized_match', 'match_analysis')
  AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
  AND language = 'en' AND environment = 'production' AND is_active IS TRUE;

UPDATE cvai.prompt_templates
SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
WHERE ((prompt_name = 'optimized_match' AND version_tag = '3.9') OR (prompt_name = 'match_analysis' AND version_tag = '1.1.0'))
  AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
  AND language = 'en' AND environment = 'production';
