import sys
from pathlib import Path

# Add the backend directory to sys.path so we can import app modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import PostgresAppSession
from app.models.prompts import PromptTemplateMaster
from app.services.prompt_service import PromptService

DYNAMIC_MAPPING = """{input_json}

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

MATCH_ANALYSIS = """{input_json}

Assess every supplied requirement separately. Use only exact facts from the CV and JD.
For DIRECT, INFERRED, or PARTIAL matches, cv_evidence must cite the explicit CV fact supporting the classification.
For MISSING or NOT_ASSESSABLE, use an empty cv_evidence string instead of inventing evidence.
Confidence is certainty in the evidence classification, not a match score. Impact is the recruiting consequence; a missing mandatory requirement is CRITICAL.
Return exactly one requirement_assessments item for every supplied requirement_id and do not add requirements.

Provide your analysis in the EXACT JSON format below.
DO NOT include any markdown formatting like ```json or ```.
DO NOT include any thinking tokens or explanations outside the JSON object.
Return ONLY valid JSON.

Expected JSON Schema:
{{
  "skill_matches": ["skill1", "skill2"],
  "inferred_skills": ["inferred1", "inferred2"],
  "missing_critical": ["missing1"],
  "semantic_reason": "A concise overall explanation grounded in the requirement assessments",
  "requirement_assessments": [
    {{
      "requirement_id": "skill_1",
      "requirement": "Python",
      "category": "SKILL",
      "mandatory": true,
      "cv_evidence": "Built Python APIs using FastAPI",
      "jd_evidence": "Python",
      "rationale": "The resume explicitly demonstrates the required technology in delivered API work.",
      "match_type": "DIRECT",
      "confidence": 0.98,
      "impact": "LOW"
    }}
  ]
}}
"""

PROFILE_EXTRACTION = """{input_json}

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

HIRING_RISK_EXPLANATION = PromptService.HIRING_RISK_DEFAULT_TEMPLATE


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
            "version_tag": "1.1.0",
            "system_instruction": MATCH_ANALYSIS,
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
        {
            "prompt_name": "hiring_risk_explanation",
            "version_tag": "1.0.0",
            "system_instruction": HIRING_RISK_EXPLANATION,
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
