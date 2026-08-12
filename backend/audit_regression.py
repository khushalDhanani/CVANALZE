import json
from pathlib import Path
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.services.experience_calculator import ExperienceCalculator
from app.services.candidate_domain_service import CandidateDomainService
from app.services.scoring_engine import ScoringEngine
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.core.rule_config_manager import RuleConfigManager
from app.core.config import settings

def run_audit():
    with open("tests/fixtures/matching_quality/regression_cvs.json") as f:
        cvs = json.load(f)

    for cv in cvs:
        # 1. Extraction
        resume = ResumeFieldExtractor.extract(cv["resume_text"], filename=f"{cv['fixture_id']}.pdf")
        from app.services.resume_normalizer import ResumeNormalizer
        normalized_resume = ResumeNormalizer.normalize(resume, cv["resume_text"])
        
        # 2. Context creation
        context = CandidateAnalysisContext.create(
            cv_text=cv["resume_text"],
            resume_json=resume,
            normalized_resume=normalized_resume,
        )
        
        job_data = {
            "id": f"job_{cv['fixture_id']}",
            "title": f"Senior {cv.get('expected_family', 'Role')}",
            "department": cv.get("expected_family", "IT"),
            "required_skills": cv.get("required_skills", []),
            "min_experience_years": cv.get("minimum_experience_years", 0),
            "vac_tax_domain": cv.get("expected_family", "IT")
        }
        
        result = ScoringEngine.evaluate_job_match(
            cv_text=cv["resume_text"],
            job=job_data,
            context=context,
        )
        
        domain_name = context.cand_tax_domain or "Unknown"
        stage0_count = len(context.cand_families) if hasattr(context, "cand_families") else 0
        mandatory_gaps = [f["requirement"] for f in result.mandatory_fails]
        
        print(f"CV: {cv['fixture_id']}")
        print(f"Domain: {domain_name}")
        print(f"Stage0 Count: {stage0_count}")
        print(f"Top Vacancy: {job_data['title']}")
        print(f"Mandatory Gaps: {mandatory_gaps}")
        print(f"Relevant Exp: {result.experience_score}")
        print(f"Final Score: {result.vacancy_fit_score}")
        print(f"Final Status: {result.vacancy_match_status}")
        print(f"PASS/FAIL: {'PASS' if result.vacancy_match_status in ['MATCHED', 'POTENTIAL_MATCH'] else 'FAIL'}")
        print("-" * 40)

if __name__ == "__main__":
    run_audit()
