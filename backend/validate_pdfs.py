import json
import fitz  # pymupdf
import logging
from pathlib import Path
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.resume_normalizer import ResumeNormalizer
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.services.scoring_engine import ScoringEngine
from app.services.match_evaluators import RequirementEvaluator, _calculate_relevant_experience
from app.services.experience_calculator import ExperienceCalculator

# suppress excessive logs
logging.getLogger("cv_analyzer").setLevel(logging.ERROR)

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

with open('tests/fixtures/matching_quality/regression_cvs.json') as f:
    cvs = json.load(f)

cv_pdf_map = {
    "cv_Shruti_Dhameliya_React_js_Developer_3_Years_of_Exp": "uploads/cv_Shruti_Dhameliya_React_js_Developer_3_Years_of_Exp_f13a7563d127d3a38a427b7b72125f041df1851c9992f6de07a9eca4bc1fbe57.pdf",
    "cv_gptsuifgr321345678o9p": "uploads/cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6.pdf",
    "cv_Utkarsh_Patil_07012026sdfgdfvdfsf": "uploads/cv_Utkarsh_Patil_07012026sdfgdfvdfsf_85050828c10dd305fcbc5fdff56761569ee6c8fea26922e870979722c10a1790.pdf",
    "cv_san1761727581": "uploads/cv_san1761727581_4f4334f97c11e4900772f7ab3a8e4dfe6b9d16c5a10edf1b288c441d57c4de65.pdf"
}

for cv in cvs:
    fixture_id = cv["fixture_id"]
    if fixture_id not in cv_pdf_map: continue
    
    pdf_path = cv_pdf_map[fixture_id]
    cv_text = extract_text_from_pdf(pdf_path)
    
    # Extraction
    resume_json = ResumeFieldExtractor.extract(cv_text, filename=f"{fixture_id}.pdf")
    
    # Normalization
    normalized_resume = ResumeNormalizer.normalize(resume_json, cv_text)
    
    # Context
    context = CandidateAnalysisContext.create(
        cv_text=cv_text,
        resume_json=resume_json,
        normalized_resume=normalized_resume
    )
    
    job_data = {
        "id": f"job_{fixture_id}",
        "title": f"Senior {cv.get('expected_family', 'Role')}",
        "department": cv.get("expected_family", "IT"),
        "required_skills": cv.get("required_skills", []),
        "min_experience_years": cv.get("minimum_experience_years", 0),
        "vac_tax_domain": cv.get("expected_family", "IT")
    }
    
    result = ScoringEngine.evaluate_job_match(
        cv_text=cv_text,
        job=job_data,
        context=context,
    )
    
    print(f"CV: {fixture_id}")
    emp_blocks = len(normalized_resume.employment) if normalized_resume.employment else 0
    
    # We want to re-run the _calculate_relevant_experience logic to print blocks safely
    from app.services.match_evaluators import _calculate_relevant_experience
    
    # Add a temporary print monkey patch to _calculate_relevant_experience
    job_ctx = JobEvaluationContext.create(job_data)
    
    relevant_years = _calculate_relevant_experience(context, job_ctx, ScoringEngine._extract_term_matches)
    
    mandatory_fails = [m.requirement if hasattr(m, 'requirement') else m.get("requirement", "") for m in getattr(result, 'mandatory_fails', [])]
    passed = "PASS" if not mandatory_fails else f"ISSUE: {mandatory_fails}"
    print(f"Result: {passed}")
    
    print(f"Relevant Employment: {emp_blocks} blocks detected")
    print(f"Parsed Dates:")
    
    valid_intervals = []
    from datetime import datetime
    for emp in normalized_resume.employment:
        emp_title = emp.job_title.normalized_value or emp.job_title.raw_value
        start = emp.interval.start_date
        end = emp.interval.end_date
        is_cur = emp.interval.is_current
        print(f"  - {emp_title}: {start} to {end} (Current: {is_cur})")
        if start:
            s_date = datetime.fromisoformat(start)
            e_date = datetime.fromisoformat(end) if end else (datetime.now() if is_cur else s_date)
            valid_intervals.append((s_date, e_date))
            
    merged = ExperienceCalculator._merge_intervals(valid_intervals)
    total_days = sum((e - s).days + 1 for s, e in merged)
    raw_merged = round(total_days / 365.25, 1)

    print(f"Relevant Years: {relevant_years} (Raw valid dates combined: {raw_merged})")
    print(f"Required Years: {job_data['min_experience_years']}")
    print("-" * 50)
