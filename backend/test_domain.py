from app.services.candidate_domain_service import CandidateDomainService
from app.core.cache import cv_result_cache_manager

def main():
    res = cv_result_cache_manager.get("cv_gptsuifgr321345678o9p")
    if not res:
        print("Not in cache")
        return
    cv_text = res.get("text") or res.get("markdown") or ""
    resume_json = res.get("parsed_json") or {}
    
    prof = CandidateDomainService.extract_candidate_domain_profile(
        cv_text=cv_text,
        resume_json=resume_json
    )
    print("Domain Profile:", prof)

if __name__ == "__main__":
    main()
