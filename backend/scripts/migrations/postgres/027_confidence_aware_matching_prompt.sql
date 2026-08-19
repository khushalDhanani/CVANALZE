-- Version the optimized prompt after strengthening per-vacancy coverage and response validation.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM cvai.prompt_templates
        WHERE prompt_name = 'optimized_match'
          AND version_tag = '3.6'
          AND tenant_id IS NULL
          AND model IS NULL
          AND target_schema IS NULL
          AND language = 'en'
          AND environment = 'production'
    ) THEN
        RAISE EXCEPTION 'optimized_match prompt version 3.6 is required before installing version 3.7';
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
    '3.7',
    'Confidence-aware evidence-grounded optimized CV matching prompt with complete per-vacancy evaluation.',
    replace(
        system_instruction,
        '12. EVIDENCE CITATION: Every field in `candidate_profile` (skills, domain, department, strengths, roles) must be justified by specific text from the CV.' || E'\n' ||
        '    For each field include only what is directly evidenced — do not infer beyond the stated facts.',
        '12. EVIDENCE CITATION: Every field in `candidate_profile` (skills, domain, department, strengths, roles) must be justified by specific text from the CV.' || E'\n' ||
        '    For each field include only what is directly evidenced — do not infer beyond the stated facts.' || E'\n' ||
        '13. VACANCY COVERAGE: Return exactly one `matched_vacancies` entry for every supplied vacancy, including low-fit vacancies.' || E'\n' ||
        '    Each entry must include a non-empty `semantic_reason` and numeric `semantic_fit_score`. Keep requirement and evidence details scoped to that vacancy.'
    ),
    $optimized_match_schema${
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "$id": "cvai://prompts/optimized_match/response-schema/v2",
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
            "required": ["vacancy_id", "semantic_reason", "semantic_fit_score"],
            "properties": {
              "vacancy_id": {"type": ["integer", "string"]},
              "semantic_reason": {"type": "string", "minLength": 1},
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
  AND version_tag = '3.6'
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
          AND version_tag = '3.7'
          AND tenant_id IS NULL
          AND model IS NULL
          AND target_schema IS NULL
          AND language = 'en'
          AND environment = 'production'
          AND strpos(system_instruction, 'VACANCY COVERAGE:') > 0
    ) THEN
        RAISE EXCEPTION 'optimized_match prompt version 3.7 did not install the required vacancy-coverage instruction';
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
