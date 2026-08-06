from app.services.cv_service import process_cv_file
import asyncio
from pathlib import Path

async def main():
    file_path = "uploads/cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6.pdf"
    content = Path(file_path).read_bytes()
    filename = Path(file_path).name

    # Reprocess
    result = await process_cv_file(filename=filename, content=content, force_reprocess=True)
    
    # Run recommendation service directly
    from app.services.recommendation_service import RecommendationService
    rec = RecommendationService.get_candidate_recommendations("cv_gptsuifgr321345678o9p")
    print("\n--- FINAL REC ---")
    print("DEPT:", rec.get("primary_department"))
    print("ROLE FIT:", rec.get("role_department_fit"))
    print("RECOMMENDATION:", rec.get("hiring_recommendation"))

if __name__ == "__main__":
    asyncio.run(main())
