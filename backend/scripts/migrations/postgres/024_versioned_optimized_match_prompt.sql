-- Make the optimized matching prompt a versioned PostgreSQL runtime dependency.
CREATE TABLE IF NOT EXISTS cvai.prompt_templates (
    prompt_id SERIAL PRIMARY KEY,
    prompt_name VARCHAR(100) NOT NULL,
    version_tag VARCHAR(50) NOT NULL,
    description VARCHAR(500),
    system_instruction TEXT NOT NULL,
    expected_schema_json TEXT,
    tenant_id VARCHAR(50),
    model VARCHAR(50),
    target_schema VARCHAR(100),
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    environment VARCHAR(50) NOT NULL DEFAULT 'production',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_prompt_templates_prompt_name ON cvai.prompt_templates (prompt_name);
CREATE INDEX IF NOT EXISTS ix_prompt_templates_tenant_id ON cvai.prompt_templates (tenant_id);

-- An execution scope may have only one active prompt, including the global NULL-valued scope.
WITH ranked_active AS (
    SELECT prompt_id,
           ROW_NUMBER() OVER (
               PARTITION BY prompt_name, COALESCE(tenant_id, ''), COALESCE(model, ''), COALESCE(target_schema, ''), language, environment
               ORDER BY updated_at DESC, prompt_id DESC
           ) AS active_rank
    FROM cvai.prompt_templates
    WHERE is_active IS TRUE
)
UPDATE cvai.prompt_templates AS prompt
SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
FROM ranked_active
WHERE prompt.prompt_id = ranked_active.prompt_id AND ranked_active.active_rank > 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_prompt_templates_active_scope
    ON cvai.prompt_templates (
        prompt_name,
        COALESCE(tenant_id, ''),
        COALESCE(model, ''),
        COALESCE(target_schema, ''),
        language,
        environment
    )
    WHERE is_active IS TRUE;

UPDATE cvai.prompt_templates
SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
WHERE prompt_name = 'optimized_match'
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
    'optimized_match',
    '3.5',
    'Default evidence-grounded optimized CV matching prompt.',
    $optimized_match_prompt$/think
{input_json}

EVIDENCE-BASED REASONING RULES:
1. Do NOT make assumptions or infer experience not explicitly supported by the CV.
2. EVERY conclusion in semantic_reason must reference specific evidence from the CV.
3. If evidence is missing for a requirement, state "No evidence found" — do not guess.
4. Do not use generic phrases like "strong experience" unless backed by specific skills, projects, or responsibilities cited from the CV.
5. Compare the candidate against each vacancy requirement item by item.
6. If there is a mismatch (department, domain, education, role, technology, skills), explicitly report it.
7. Never increase semantic_fit_score based on assumptions — score only on verified evidence.
8. If there is no genuine match with any active vacancy, set active_vacancy_summary to "No suitable active vacancy found.".
9. IMPORTANT (EXPERIENCE): Calculate `relevant_experience_years` strictly by summing the total duration of the chronological work history. E.g., "2014 to 2015" (1 yr) + "2023 to present" (~3 yrs) = 4.0 years. Do NOT default to 0.0 if dates are present.
10. IMPORTANT (DOMAIN): `professional_domain` MUST be strictly selected from this list: [{domain_list_str}]. Do NOT invent domains.
    If NONE of the listed domains genuinely fits the candidate, set `professional_domain` to "NO_SUITABLE_MATCH" and set `professional_domains` to ["NO_SUITABLE_MATCH"].
11. IMPORTANT (DEPARTMENT): `recommended_department` MUST be selected from this list: [{dept_list_str}]. Do NOT invent department names.
    If no department fits, set `recommended_department` to "NO_SUITABLE_MATCH".
12. EVIDENCE CITATION: Every field in `candidate_profile` (skills, domain, department, strengths, roles) must be justified by specific text from the CV.
    For each field include only what is directly evidenced — do not infer beyond the stated facts.

INSTRUCTIONS:
Return ONLY valid JSON matching the exact schema below without markdown wrapper, thinking tokens, or extra commentary.

Expected JSON Schema:
{{
  "candidate_profile": {{
    "core_skills": ["List of explicitly stated skills"],
    "inferred_skills": ["List of logical inferred skills, e.g. React implies JavaScript"],
    "relevant_experience_years": 5.0,
    "education_domains": ["Extracted education domains/degrees"],
    "certifications": ["Extracted certifications"],
    "current_role": "Current or most recent job title",
    "professional_domains": ["Extracted professional domain areas"],
    "recommended_department": "Most suitable department for candidate",
    "professional_domain": "Candidate's specialized professional domain",
    "strengths": ["Key candidate strengths from skills, experience, projects"],
    "suitable_job_roles": ["List of suitable market job roles"]
  }},
  "active_vacancy_summary": "Summary of genuine active vacancy match if genuine match exists; otherwise 'No suitable active vacancy found.'",
  "ai_career_summary": "Independent AI analysis of candidate's profile, strengths, recommended department, and suitable job roles.",
  "matched_vacancies": [
    {{
      "vacancy_id": 101,
      "semantic_reason": "Clear explanation of semantic fit based on CV evidence, citing specific skills, projects, or roles. If no fit, state 'No evidence found for X requirement'.",
      "inferred_skills": ["Inferred skills relevant to this specific vacancy"],
      "matched_skills": ["Skills from required_skills present in CV"],
      "missing_critical": ["Critical requirements missing"],
      "semantic_fit_score": 85.0,
      "career_transition_detected": false,
      "career_transition_note": "Optional notes if dynamic career transition detected",
      "classified_requirements": [
        {{
          "requirement_id": "req_1",
          "description": "Requirement description",
          "tier": "MANDATORY",
          "status": "SATISFIED",
          "failure_reason": null
        }}
      ],
      "evidence_snippets": {{
        "req_1": {{
          "cv_evidence": "Quote or verified fact from CV text",
          "vacancy_evidence": "Exact requirement text from vacancy"
        }}
      }}
    }}
  ]
}}
$optimized_match_prompt$,
    '{"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"cvai://prompts/optimized_match/response-schema/v1","type":"object","required":["candidate_profile","active_vacancy_summary","ai_career_summary","matched_vacancies"],"properties":{"candidate_profile":{"type":"object"},"active_vacancy_summary":{"type":"string"},"ai_career_summary":{"type":"string"},"matched_vacancies":{"type":"array"}}}',
    NULL,
    NULL,
    NULL,
    'en',
    'production',
    TRUE
WHERE NOT EXISTS (
    SELECT 1
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
SET description = 'Default evidence-grounded optimized CV matching prompt.',
    expected_schema_json = '{"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"cvai://prompts/optimized_match/response-schema/v1","type":"object","required":["candidate_profile","active_vacancy_summary","ai_career_summary","matched_vacancies"],"properties":{"candidate_profile":{"type":"object"},"active_vacancy_summary":{"type":"string"},"ai_career_summary":{"type":"string"},"matched_vacancies":{"type":"array"}}}',
    is_active = TRUE,
    updated_at = CURRENT_TIMESTAMP
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
