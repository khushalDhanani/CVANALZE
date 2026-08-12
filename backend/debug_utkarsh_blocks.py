import json
import logging
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.resume_normalizer import ResumeNormalizer
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.services.scoring_engine import ScoringEngine
from app.services.match_evaluators import _calculate_relevant_experience
import fitz

logging.getLogger("cv_analyzer").setLevel(logging.ERROR)

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

cv_pdf_map = {
    "cv_Shruti_Dhameliya_React_js_Developer_3_Years_of_Exp": "uploads/cv_Shruti_Dhameliya_React_js_Developer_3_Years_of_Exp_f13a7563d127d3a38a427b7b72125f041df1851c9992f6de07a9eca4bc1fbe57.pdf",
    "cv_gptsuifgr321345678o9p": "uploads/cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6.pdf",
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
    
    # We will simulate the exact block calculation for Utkarsh
    if fixture_id == "cv_Utkarsh_Patil_07012026sdfgdfvdfsf":
        print(f"\n=======================")
        print(f"CV: {fixture_id}")
        
        job_family = job_ctx.vac_family if job_ctx.vac_family not in (None, "Unknown") else None
        job_domain = job_ctx.vac_tax_domain if job_ctx.vac_tax_domain not in (None, "Unknown") else None
        print(f"Vacancy Domain: {job_domain}, Family: {job_family}")
        
        for emp in context.normalized_resume.employment:
            emp_title = emp.job_title.normalized_value or emp.job_title.raw_value or ""
            emp_text = " ".join([emp_title, *emp.responsibilities, *emp.evidence]).lower()
            print(f"\nBlock Title: {emp_title}")
            print(f"Responsibilities/Evidence length: {len(emp_text)}")
            
            from app.services.job_taxonomy import DynamicTaxonomyService, TaxonomyClassifier
            block_tax = DynamicTaxonomyService.resolve_vacancy_domain_and_family(
                title=emp_title,
                department="",
                description=" ".join(emp.responsibilities),
                required_skills=emp.evidence,
                skip_vector=False
            )
            block_family = getattr(block_tax, "job_family", getattr(block_tax, "industry_department", None))
            block_domain = getattr(block_tax, "domain", getattr(block_tax, "industry_domain", None))
            print(f"Block Domain: {block_domain}, Family: {block_family}")
            
            evidence_score = 0.0
            
            is_same_canonical_domain = False
            if block_domain and block_domain != "Unknown" and job_domain and job_domain != "Unknown":
                if block_domain.strip().lower() == job_domain.strip().lower():
                    is_same_canonical_domain = True

            if job_family and block_family:
                is_parent_child = False
                if is_same_canonical_domain and (job_family.strip().lower() == job_domain.strip().lower() or block_family.strip().lower() == block_domain.strip().lower()):
                    is_parent_child = True

                if TaxonomyClassifier.are_families_compatible([block_family], job_family):
                    evidence_score += 5.0
                    print(f"  +5.0 (Taxonomy Compatible)")
                elif is_same_canonical_domain and is_parent_child:
                    evidence_score += 5.0
                    print(f"  +5.0 (Same Canonical Domain & Parent/Child)")
                elif is_same_canonical_domain:
                    evidence_score += 2.5
                    print(f"  +2.5 (Same Canonical Domain)")
                else:
                    evidence_score -= 5.0
                    print(f"  -5.0 (Taxonomy Contradiction)")
            
            print(f"Final Block Evidence Score: {evidence_score}")
