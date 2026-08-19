-- Version the optimized prompt to produce recruiter-actionable decision narratives for every vacancy.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM cvai.prompt_templates
        WHERE prompt_name = 'optimized_match'
          AND version_tag = '3.7'
          AND tenant_id IS NULL
          AND model IS NULL
          AND target_schema IS NULL
          AND language = 'en'
          AND environment = 'production'
    ) THEN
        RAISE EXCEPTION 'optimized_match prompt version 3.7 is required before installing version 3.8';
    END IF;
END $$;

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
    '3.8',
    'Evidence-grounded optimized CV matching prompt with detailed recruiter decision narratives.',
    replace(
        replace(
            system_instruction,
            $old_rule$13. VACANCY COVERAGE: Return exactly one `matched_vacancies` entry for every supplied vacancy, including low-fit vacancies.
    Each entry must include a non-empty `semantic_reason` and numeric `semantic_fit_score`. Keep requirement and evidence details scoped to that vacancy.$old_rule$,
            $new_rule$13. VACANCY COVERAGE: Return exactly one `matched_vacancies` entry for every supplied vacancy, including low-fit vacancies.
    Each entry must include a non-empty `semantic_reason` and numeric `semantic_fit_score`. Keep requirement and evidence details scoped to that vacancy.
14. DECISION NARRATIVES: For every vacancy, return `top_strength`, `main_concern`, and `ai_match_explanation` as separate recruiter-ready sections of 2-3 complete sentences each.
    `top_strength` must name the single strongest match and cite a specific skill, project, achievement, role, or length of experience together with the related position requirement.
    `main_concern` must explain the largest role-specific gap or risk, such as a missing skill, experience mismatch, employment gap, or qualification mismatch. If the resume or role description lacks enough information, say what is missing instead of guessing.
    `ai_match_explanation` must explain the numeric score by comparing concrete details from the candidate's background with specific position requirements, including both supporting and limiting evidence where available.
    Write like an HR professional recording a concise assessment. Vary sentence openings and naturally use phrases such as "the candidate's background", "their experience", "the resume shows", or "based on their profile".
    Avoid repeatedly saying "CV", "the CV", "CV evidence", or "CV/JD comparison". Do not start every section or sentence with the same phrase.
    Do not use vague phrases such as "good fit", "strong candidate", or "relevant experience" without naming the supporting candidate and role facts. Do not combine the three sections.$new_rule$
        ),
        $old_response$      "semantic_reason": "Clear explanation of semantic fit based on CV evidence, citing specific skills, projects, or roles. If no fit, state 'No evidence found for X requirement'.",$old_response$,
        $new_response$      "semantic_reason": "Backward-compatible concise semantic reason grounded in candidate and role evidence.",
      "top_strength": "Their five years of Python API development are the clearest match for this backend role. That experience directly supports the position's Python and REST API requirements.",
      "main_concern": "AWS deployment is required, but the resume does not mention cloud ownership or an AWS project. This should be verified during screening rather than inferred from general backend experience.",
      "ai_match_explanation": "The 82 percent rating reflects direct alignment on Python, REST APIs, and five years of backend delivery. It is held back by the missing AWS evidence and limited detail about production scale.",$new_response$
    ),
    $optimized_match_schema${
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "$id": "cvai://prompts/optimized_match/response-schema/v3",
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
            "required": ["vacancy_id", "semantic_reason", "top_strength", "main_concern", "ai_match_explanation", "semantic_fit_score"],
            "properties": {
              "vacancy_id": {"type": ["integer", "string"]},
              "semantic_reason": {"type": "string", "minLength": 1},
              "top_strength": {"type": "string", "minLength": 80, "maxLength": 1200},
              "main_concern": {"type": "string", "minLength": 80, "maxLength": 1200},
              "ai_match_explanation": {"type": "string", "minLength": 80, "maxLength": 1200},
              "semantic_fit_score": {"type": "number", "minimum": 0, "maximum": 100},
              "classified_requirements": {"type": "array"},
              "evidence_snippets": {"type": "object"}
            }
          }
        }
      }
    }$optimized_match_schema$,
    tenant_id,
    model,
    target_schema,
    language,
    environment,
    FALSE
FROM cvai.prompt_templates
WHERE prompt_name = 'optimized_match'
  AND version_tag = '3.7'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production'
ORDER BY prompt_id DESC
LIMIT 1;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM cvai.prompt_templates
        WHERE prompt_name = 'optimized_match'
          AND version_tag = '3.8'
          AND tenant_id IS NULL
          AND model IS NULL
          AND target_schema IS NULL
          AND language = 'en'
          AND environment = 'production'
          AND strpos(system_instruction, 'DECISION NARRATIVES:') > 0
          AND strpos(system_instruction, '"top_strength"') > 0
          AND strpos(system_instruction, '"main_concern"') > 0
          AND strpos(system_instruction, '"ai_match_explanation"') > 0
    ) THEN
        RAISE EXCEPTION 'optimized_match prompt version 3.8 did not install the detailed narrative contract';
    END IF;
END $$;

UPDATE cvai.prompt_templates
SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
WHERE prompt_name = 'optimized_match'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production'
  AND is_active IS TRUE;

UPDATE cvai.prompt_templates
SET is_active = TRUE, updated_at = CURRENT_TIMESTAMP
WHERE prompt_name = 'optimized_match'
  AND version_tag = '3.8'
  AND tenant_id IS NULL
  AND model IS NULL
  AND target_schema IS NULL
  AND language = 'en'
  AND environment = 'production'
  AND prompt_id = (
      SELECT MAX(prompt_id)
      FROM cvai.prompt_templates
      WHERE prompt_name = 'optimized_match'
        AND version_tag = '3.8'
        AND tenant_id IS NULL
        AND model IS NULL
        AND target_schema IS NULL
        AND language = 'en'
        AND environment = 'production'
  );
