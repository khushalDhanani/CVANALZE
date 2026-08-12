import json
import logging
import re
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
    "cv_Utkarsh_Patil_07012026sdfgdfvdfsf": "uploads/cv_Utkarsh_Patil_07012026sdfgdfvdfsf_85050828c10dd305fcbc5fdff56761569ee6c8fea26922e870979722c10a1790.pdf",
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
    job_ctx = JobEvaluationContext.create(job_data)
    print("Job title words:", job_ctx.title_words)
    print("Job required skills:", job_ctx.required_skills)
    
    for emp in context.normalized_resume.employment:
        emp_title = emp.job_title.normalized_value or emp.job_title.raw_value or ""
        emp_text = " ".join([emp_title, *emp.responsibilities, *emp.evidence]).lower()
        
        # Title words
        title_words = set(re.findall(r"\w+", emp_title.lower()))
        print("Emp title words:", title_words)
        
        from app.core.rule_config_manager import RuleConfigManager
        config = RuleConfigManager.get_config()
        noise_words = set(config.scoring.match.term_matching.noise_words)
        
        filtered_title_words = title_words - noise_words
        filtered_job_words = job_ctx.title_words - noise_words
        print("Filtered emp title words:", filtered_title_words)
        print("Filtered job title words:", filtered_job_words)
        print("Intersection:", filtered_title_words.intersection(filtered_job_words))
        
        # Skills density
        matched, _ = ScoringEngine._extract_term_matches(emp_text, job_ctx.required_skills)
        print("Matched required skills:", matched)
        
