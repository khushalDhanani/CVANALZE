import json
import logging
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.resume_normalizer import ResumeNormalizer
from app.schemas.candidate_context import CandidateAnalysisContext
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
    "cv_gptsuifgr321345678o9p": "uploads/cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6.pdf",
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
    
    print(f"Context Candidate Experience (Gemma/Total): {context.candidate_experience}")
    print(f"Has Relevant Experience boolean checks:")
    print(f"Is None: {context.candidate_experience is None}")
    if context.candidate_experience is not None:
        print(f"Is <= 0: {context.candidate_experience <= 0}")
