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

for cv_info in cvs:
    fid = cv_info["fixture_id"]
    if fid not in cv_pdf_map: continue
    
    cv_text = extract_text_from_pdf(cv_pdf_map[fid])
    resume_json = ResumeFieldExtractor.extract(cv_text, filename=f"{fid}.pdf")
    
    candidate_ctx = ResumeNormalizer.normalize(resume_json, cv_text)
    reqs = {
        "job_id": "test",
        "title": "test",
        "department": "test",
        "taxonomy": {"family": cv_info["expected_family"], "domain": cv_info["expected_family"]},
        "required_skills": cv_info["required_skills"],
        "minimum_experience_years": cv_info["minimum_experience_years"]
    }
    vacancy_ctx = JobEvaluationContext(**reqs)
    
    scoring_engine = ScoringEngine()
    result = scoring_engine.evaluate(candidate_ctx, vacancy_ctx)
    
    print(f"\n=======================")
    print(f"CV: {fid}")
    print(f"Final Score Result: {result.status.value}")
    
    for ev in result.evidence:
        if ev.component == "experience" and ev.details:
            print(f"Experience Evidence: {ev.details}")
        if ev.component == "experience_blocks":
            print(f"Experience Blocks Evidence: {ev.details}")
            
