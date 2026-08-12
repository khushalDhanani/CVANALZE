import sys
from pathlib import Path

# Add the backend directory to sys.path so we can import app modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import PostgresAppSession
from app.models.prompts import PromptTemplateMaster

DYNAMIC_MAPPING = """/think
{input_json}

Provide your analysis in the EXACT JSON format below.
DO NOT include any markdown formatting like ```json or ```.
DO NOT include any thinking tokens or explanations outside the JSON object.
Return ONLY valid JSON.

Expected JSON Schema:
{{
  "matched_vacancies": [
    {{
      "vacancy_id": 1334,
      "semantic_reason": "Candidate's experience and skills directly correspond to the requirements of the vacancy record.",
      "inferred_skills": ["relevant_skill_1", "relevant_skill_2"]
    }}
  ]
}}
"""

MATCH_ANALYSIS = """/think
{input_json}

Provide your analysis in the EXACT JSON format below.
DO NOT include any markdown formatting like ```json or ```.
DO NOT include any thinking tokens or explanations outside the JSON object.
Return ONLY valid JSON.

Expected JSON Schema:
{{
  "skill_matches": ["skill1", "skill2"],
  "inferred_skills": ["inferred1", "inferred2"],
  "missing_critical": ["missing1"],
  "semantic_reason": "A brief explanation of why the candidate fits or lacks fit"
}}
"""

OPTIMIZED_MATCH = """/think
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
"""

PROFILE_EXTRACTION = """/no_think
{input_json}

Provide your analysis in the EXACT JSON format below.
DO NOT include any markdown formatting like ```json or ```.
DO NOT include any thinking tokens or explanations outside the JSON object.
Return ONLY valid JSON that conforms to this schema:

{{
  "education_domains": ["List of extracted education domains, e.g. Computer Science"],
  "professional_domains": ["List of extracted professional domains, e.g. Software Engineering"],
  "current_domain": "The most recent and primary professional domain",
  "current_role": "The most recent job title or role",
  "previous_roles": ["List of previous job titles"],
  "career_transitions": [
    {{
      "from_role": "Previous role or domain",
      "to_role": "New role or domain",
      "reason_inferred": "Inferred reason for transition based on CV",
      "evidence": "Evidence from CV supporting this transition"
    }}
  ],
  "core_skills": ["List of core technical and soft skills demonstrated"],
  "relevant_experience_years": 5.5,
  "timeline": [
    {{
      "title": "Job Title or Degree",
      "organization": "Company or University",
      "start_date": "YYYY-MM",
      "end_date": "YYYY-MM or null if present",
      "description": "Brief description of responsibilities or achievements"
    }}
  ],
  "confidence": "HIGH, MEDIUM, LOW, or UNCERTAIN",
  "evidence_notes": "Explanation of inferences and any conflicting evidence"
}}
"""

WORK_EXPERIENCE = """You are a production-grade CV work-experience extraction engine.

Your task is to extract employment evidence from the OCR text provided.
You must output a structured JSON document conforming to the provided schema.

INPUT DATA

Candidate ID: {candidate_id}
OCR Text:
{ocr_text}

IMPORTANT RULES

1. Extract ONLY work-experience information supported by the OCR text.
2. NEVER invent:
   - Company names
   - Job titles
   - Dates
   - Employment types
   - Locations
3. Preserve the original extracted text and populate both original and normalized fields where possible.
4. Identify employment records from:
   - Tables
   - Paragraphs
   - Bullet points
   - Timelines
   - Company-wise sections
   - Position-wise sections
   - Broken OCR rows
5. Recognize date formats such as:
   - 01 August 2025
   - 01st August 2025
   - August 2025
   - Aug 2025
   - 08/2025
   - 2025-08
   - 01/08/2025
   - 2020 - 2025
   - Since August 2025
6. Treat these as current-employment indicators (is_current = true):
   - Present
   - Current
   - Continue
   - Continuing
   - Till Date
   - To Date
   - Ongoing
   - Now
   - Currently Working
7. Distinguish employment types when explicit:
   - full_time, part_time, contract, temporary, freelance, self_employed, apprenticeship, internship, training, volunteer, unknown
   - Do not assume full_time for internships/apprenticeships unless explicitly stated.
8. IGNORE dates belonging to:
   - Date of birth
   - Education
   - Certifications
   - Declaration date
   - Document creation date
   unless they clearly belong to employment.
9. Flag ambiguous numeric dates or missing start dates with warnings.
10. Flag reversed or invalid date ranges.
11. Preserve uncertain company names rather than silently correcting them.
12. DO NOT calculate final experience days/years. DO NOT output final experience totals.
13. Output valid JSON matching the requested schema.
"""


def seed_prompts():
    print("Seeding prompt templates to DB...")
    templates = [
        {
            "prompt_name": "dynamic_mapping",
            "version_tag": "2.0.0",
            "system_instruction": DYNAMIC_MAPPING,
        },
        {
            "prompt_name": "match_analysis",
            "version_tag": "1.0.0",
            "system_instruction": MATCH_ANALYSIS,
        },
        {
            "prompt_name": "optimized_match",
            "version_tag": "2.0.0",
            "system_instruction": OPTIMIZED_MATCH,
        },
        {
            "prompt_name": "profile_extraction",
            "version_tag": "1.0.0",
            "system_instruction": PROFILE_EXTRACTION,
        },
        {
            "prompt_name": "work_experience_extraction_v1",
            "version_tag": "1.0.0",
            "system_instruction": WORK_EXPERIENCE,
        },
    ]

    with PostgresAppSession() as db:
        for t in templates:
            existing = db.query(PromptTemplateMaster).filter(
                PromptTemplateMaster.prompt_name == t["prompt_name"],
                PromptTemplateMaster.tenant_id.is_(None),
                PromptTemplateMaster.model.is_(None),
                PromptTemplateMaster.language == "en",
                PromptTemplateMaster.environment == "production"
            ).first()
            if not existing:
                print(f"Inserting {t['prompt_name']}")
                new_prompt = PromptTemplateMaster(
                    prompt_name=t["prompt_name"],
                    version_tag=t["version_tag"],
                    system_instruction=t["system_instruction"],
                    is_active=True,
                )
                db.add(new_prompt)
            else:
                print(f"Skipping {t['prompt_name']}, already exists.")
        db.commit()
    print("Done seeding prompts.")

if __name__ == "__main__":
    seed_prompts()
