-- Add explicit conclusion field to the per-requirement evidence chain in both prompt schemas.
-- match_analysis: 1.1.0 -> 1.2.0 | optimized_match: 3.9 -> 4.0
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM cvai.prompt_templates
        WHERE prompt_name = 'match_analysis' AND version_tag = '1.1.0'
          AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
          AND language = 'en' AND environment = 'production'
    ) THEN
        RAISE EXCEPTION 'match_analysis prompt version 1.1.0 is required before installing version 1.2.0';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM cvai.prompt_templates
        WHERE prompt_name = 'optimized_match' AND version_tag = '3.9'
          AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
          AND language = 'en' AND environment = 'production'
    ) THEN
        RAISE EXCEPTION 'optimized_match prompt version 3.9 is required before installing version 4.0';
    END IF;
END $$;

INSERT INTO cvai.prompt_templates (
    prompt_name, version_tag, description, system_instruction, expected_schema_json,
    tenant_id, model, target_schema, language, environment, is_active
)
SELECT
    'match_analysis',
    '1.2.0',
    'Per-requirement evidence chain: requirement -> jd_evidence -> cv_evidence -> match_type -> conclusion -> rationale -> impact.',
    replace(
        replace(
            system_instruction,
            E'For DIRECT, INFERRED, or PARTIAL matches, cv_evidence must cite the explicit CV fact supporting the classification.',
            $new_instructions$For each requirement, follow this evidence chain: jd_evidence -> cv_evidence -> match_type -> conclusion -> rationale -> impact.
For DIRECT, INFERRED, or PARTIAL matches, cv_evidence must cite the explicit CV fact supporting the classification.
conclusion must be one recruiter-facing verdict sentence, e.g. "Python is directly met by the candidate." or "Kubernetes cannot be confirmed from the CV."
rationale explains the evidence and reasoning behind the match_type classification.$new_instructions$
        ),
        $old_example$      "cv_evidence": "Built Python APIs using FastAPI",
      "jd_evidence": "Python",
      "rationale": "The resume explicitly demonstrates the required technology in delivered API work.",
      "match_type": "DIRECT",$old_example$,
        $new_example$      "jd_evidence": "Python",
      "cv_evidence": "Built Python APIs using FastAPI",
      "match_type": "DIRECT",
      "conclusion": "Python is directly met by the candidate.",
      "rationale": "The resume explicitly demonstrates the required technology in delivered API work.",$new_example$
    ),
    $match_analysis_schema_v3${
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "$id": "cvai://prompts/match_analysis/response-schema/v3",
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
            "required": ["requirement_id", "requirement", "category", "mandatory", "jd_evidence", "cv_evidence", "match_type", "conclusion", "rationale", "confidence", "impact"],
            "properties": {
              "requirement_id": {"type": "string", "minLength": 1},
              "requirement": {"type": "string", "minLength": 1},
              "category": {"type": "string", "minLength": 1},
              "mandatory": {"type": "boolean"},
              "jd_evidence": {"type": "string", "minLength": 1},
              "cv_evidence": {"type": "string"},
              "match_type": {"enum": ["DIRECT", "INFERRED", "PARTIAL", "MISSING", "NOT_ASSESSABLE"]},
              "conclusion": {"type": "string", "minLength": 1},
              "rationale": {"type": "string", "minLength": 1},
              "confidence": {"type": "number", "minimum": 0, "maximum": 1},
              "impact": {"enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]}
            }
          }
        }
      }
    }$match_analysis_schema_v3$,
    tenant_id, model, target_schema, language, environment, FALSE
FROM cvai.prompt_templates
WHERE prompt_name = 'match_analysis' AND version_tag = '1.1.0'
  AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
  AND language = 'en' AND environment = 'production'
  AND NOT EXISTS (
      SELECT 1 FROM cvai.prompt_templates existing
      WHERE existing.prompt_name = 'match_analysis' AND existing.version_tag = '1.2.0'
        AND existing.tenant_id IS NULL AND existing.model IS NULL AND existing.target_schema IS NULL
        AND existing.language = 'en' AND existing.environment = 'production'
  )
ORDER BY prompt_id DESC
LIMIT 1;

INSERT INTO cvai.prompt_templates (
    prompt_name, version_tag, description, system_instruction, expected_schema_json,
    tenant_id, model, target_schema, language, environment, is_active
)
SELECT
    prompt_name,
    '4.0',
    'Evidence-grounded optimized CV matching with per-requirement evidence chain including explicit conclusion field.',
    replace(
        replace(
            system_instruction,
            $old_req_rules$16. Copy requirement, category, mandatory, and jd_evidence from the supplied requirement. Mark mandatory only from the supplied flag.
17. cv_evidence must be an exact CV quote or fact for DIRECT, INFERRED, and PARTIAL.
    Use an empty string for MISSING or NOT_ASSESSABLE; never invent evidence.
18. match_type must be DIRECT, INFERRED, PARTIAL, MISSING, or NOT_ASSESSABLE. Explain the classification in rationale.
19. confidence is evidence certainty from 0.0 to 1.0, not a match score.
    impact is CRITICAL, HIGH, MEDIUM, or LOW and cannot alter deterministic scoring.
20. A missing mandatory requirement must have CRITICAL impact.$old_req_rules$,
            $new_req_rules$16. Copy requirement, category, mandatory, and jd_evidence from the supplied requirement. Mark mandatory only from the supplied flag.
17. For each requirement, follow the evidence chain: jd_evidence -> cv_evidence -> match_type -> conclusion -> rationale -> impact.
18. cv_evidence must be an exact CV quote or fact for DIRECT, INFERRED, and PARTIAL.
    Use an empty string for MISSING or NOT_ASSESSABLE; never invent evidence.
19. match_type must be DIRECT, INFERRED, PARTIAL, MISSING, or NOT_ASSESSABLE.
20. conclusion must be one recruiter-facing verdict sentence, e.g. "Python is directly met." or "Kubernetes cannot be confirmed from the CV."
21. rationale explains the evidence and reasoning behind the match_type classification.
22. confidence is evidence certainty from 0.0 to 1.0, not a match score.
    impact is CRITICAL, HIGH, MEDIUM, or LOW and cannot alter deterministic scoring.
23. A missing mandatory requirement must have CRITICAL impact.$new_req_rules$
        ),
        $old_optimized_example$        "cv_evidence": "Built Python APIs using FastAPI",
          "jd_evidence": "Python",
          "rationale": "The resume directly demonstrates the required technology in delivered API work.",
          "match_type": "DIRECT",$old_optimized_example$,
        $new_optimized_example$        "jd_evidence": "Python",
          "cv_evidence": "Built Python APIs using FastAPI",
          "match_type": "DIRECT",
          "conclusion": "Python is directly met by the candidate.",
          "rationale": "The resume directly demonstrates the required technology in delivered API work.",$new_optimized_example$
    ),
    $optimized_match_schema_v5${
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "$id": "cvai://prompts/optimized_match/response-schema/v5",
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
                  "required": ["requirement_id", "requirement", "category", "mandatory", "jd_evidence", "cv_evidence", "match_type", "conclusion", "rationale", "confidence", "impact"],
                  "properties": {
                    "requirement_id": {"type": "string", "minLength": 1},
                    "requirement": {"type": "string", "minLength": 1},
                    "category": {"type": "string", "minLength": 1},
                    "mandatory": {"type": "boolean"},
                    "jd_evidence": {"type": "string", "minLength": 1},
                    "cv_evidence": {"type": "string"},
                    "match_type": {"enum": ["DIRECT", "INFERRED", "PARTIAL", "MISSING", "NOT_ASSESSABLE"]},
                    "conclusion": {"type": "string", "minLength": 1},
                    "rationale": {"type": "string", "minLength": 1},
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
    }$optimized_match_schema_v5$,
    tenant_id, model, target_schema, language, environment, FALSE
FROM cvai.prompt_templates
WHERE prompt_name = 'optimized_match' AND version_tag = '3.9'
  AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
  AND language = 'en' AND environment = 'production'
  AND NOT EXISTS (
      SELECT 1 FROM cvai.prompt_templates existing
      WHERE existing.prompt_name = 'optimized_match' AND existing.version_tag = '4.0'
        AND existing.tenant_id IS NULL AND existing.model IS NULL AND existing.target_schema IS NULL
        AND existing.language = 'en' AND existing.environment = 'production'
  )
ORDER BY prompt_id DESC
LIMIT 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM cvai.prompt_templates
        WHERE prompt_name = 'match_analysis' AND version_tag = '1.2.0'
          AND strpos(system_instruction, 'conclusion must be one recruiter-facing verdict sentence') > 0
          AND strpos(expected_schema_json, 'response-schema/v3') > 0
    ) THEN
        RAISE EXCEPTION 'match_analysis prompt version 1.2.0 did not install the conclusion field contract';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM cvai.prompt_templates
        WHERE prompt_name = 'optimized_match' AND version_tag = '4.0'
          AND strpos(system_instruction, 'conclusion must be one recruiter-facing verdict sentence') > 0
          AND strpos(expected_schema_json, 'response-schema/v5') > 0
    ) THEN
        RAISE EXCEPTION 'optimized_match prompt version 4.0 did not install the conclusion field contract';
    END IF;
END $$;

UPDATE cvai.prompt_templates
SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
WHERE prompt_name IN ('optimized_match', 'match_analysis')
  AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
  AND language = 'en' AND environment = 'production' AND is_active IS TRUE;

UPDATE cvai.prompt_templates
SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
WHERE ((prompt_name = 'optimized_match' AND version_tag = '4.0')
    OR (prompt_name = 'match_analysis' AND version_tag = '1.2.0'))
  AND tenant_id IS NULL AND model IS NULL AND target_schema IS NULL
  AND language = 'en' AND environment = 'production';
