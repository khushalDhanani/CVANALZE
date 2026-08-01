import json

PROMPT_VERSION = "1.0"

def build_profile_extraction_prompt(cv_text: str) -> str:
    """
    Builds a strict JSON-only prompt for Qwen to extract a DynamicCandidateProfile
    from CV text without any hardcoded assumptions.
    """
    structured_input = {
        "task_instructions": (
            "Act as an expert HR Profile Extraction Engine. "
            "Analyze the candidate_cv_markdown and extract a highly structured DynamicCandidateProfile. "
            "CRITICAL RULES: "
            "1. Do not hardcode any industry, role, degree, skill, or domain mapping. "
            "2. Dynamically derive the candidate's profile entirely from the provided CV evidence. "
            "3. Independently analyze: Education -> Experience -> Role Timeline -> Skills -> Projects -> Certifications -> Achievements. "
            "4. Prioritize recent and demonstrated professional capability over historical or unrelated background. "
            "5. Detect career or domain transitions automatically from chronological evidence. "
            "6. Never assume a candidate belongs to a domain based solely on a degree, title, or keyword without supporting evidence. "
            "7. If evidence is insufficient or conflicting, set confidence to 'UNCERTAIN' and explain in evidence_notes. "
            "8. Calculate relevant_experience_years logically by examining the timeline and durations of roles. "
            "9. Do not infer experience or skills not explicitly stated in the CV. "
            "10. For every extracted field, there must be corresponding evidence in the CV. If no evidence exists, omit the field or set it to empty. "
            "11. Never use generic terms like 'strong communication skills' unless the CV explicitly mentions them."
        ),
        "candidate_cv_markdown": cv_text[:7500],
    }

    input_json = json.dumps(structured_input, indent=2, ensure_ascii=False)

    prompt = f"""/no_think
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
    return prompt
