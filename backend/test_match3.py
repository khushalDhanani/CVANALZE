import asyncio
from app.services.match_service import MatchService
from app.services.cv_service import process_cv_task_sync

def main():
    file_path = "uploads/cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6.pdf"
    res = process_cv_task_sync(file_path, tenant_id="GLOBAL", force_reprocess=True)
    openings = res.get("match_analysis", {}).get("suitable_openings", [])
    for o in openings[:2]:
        print(f"{o.get('job_title')}: score={o.get('score')} | skills_score={o.get('skills_score')} | domain_score={o.get('domain_score')}")
        print(f"matched_skills: {o.get('matched_skills')}")
        print(f"missing_skills: {o.get('missing_skills')}")
        print("---")

if __name__ == "__main__":
    main()
