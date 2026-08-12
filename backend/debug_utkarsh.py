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

with open('tests/fixtures/matching_quality/regression_cvs.json') as f:
    cvs = json.load(f)

cv_pdf_map = {
    "cv_Shruti_Dhameliya_React_js_Developer_3_Years_of_Exp": "uploads/cv_Shruti_Dhameliya_React_js_Developer_3_Years_of_Exp_f13a7563d127d3a38a427b7b72125f041df1851c9992f6de07a9eca4bc1fbe57.pdf",
    "cv_gptsuifgr321345678o9p": "uploads/cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6.pdf",
    "cv_Utkarsh_Patil_07012026sdfgdfvdfsf": "uploads/cv_Utkarsh_Patil_07012026sdfgdfvdfsf_85050828c10dd305fcbc5fdff56761569ee6c8fea26922e870979722c10a1790.pdf",
}

for cv in cvs:
    fixture_id = cv["fixture_id"]
    if fixture_id not in cv_pdf_map: continue
    
    pdf_path = cv_pdf_map[fixture_id]
    cv_text = extract_text_from_pdf(pdf_path)
    
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
    
    print(f"\n=======================")
    print(f"CV: {fixture_id}")
    for ev in result.evidence:
        print(ev)
