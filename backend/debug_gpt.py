import json
import logging
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.resume_normalizer import ResumeNormalizer
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.services.scoring_engine import ScoringEngine
import fitz

logging.getLogger("cv_analyzer").setLevel(logging.ERROR)

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

cv_pdf_map = {
    "cv_gptsuifgr321345678o9p": "uploads/cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6.pdf",
}

with open('tests/fixtures/matching_quality/regression_cvs.json') as f:
    cvs = json.load(f)

for cv in cvs:
    fixture_id = cv["fixture_id"]
    if fixture_id not in cv_pdf_map: continue
    
    cv_text = extract_text_from_pdf(cv_pdf_map[fixture_id])
    resume_json = ResumeFieldExtractor.extract(cv_text, filename=f"{fixture_id}.pdf")
    normalized_resume = ResumeNormalizer.normalize(resume_json, cv_text)
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
    
    mandatory_fails = [m.requirement if hasattr(m, 'requirement') else m.get("requirement", "") for m in getattr(result, 'mandatory_fails', [])]
    passed = "PASS" if not mandatory_fails else f"ISSUE: {mandatory_fails}"
    print(f"\n=======================")
    print(f"CV: {fixture_id}")
    print(f"Result: {passed}")
    print(f"Mandatory Fails: {mandatory_fails}")
    print(f"Score status: {result.status.value}")
