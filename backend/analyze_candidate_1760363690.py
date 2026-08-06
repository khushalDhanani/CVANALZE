import asyncio
import json
from pathlib import Path
from app.services.cv_service import process_cv_file
from app.services.recommendation_service import RecommendationService
from app.core.cache import match_result_cache_manager

async def main():
    match_result_cache_manager.clear()
    
    file_path = "uploads/cv_1760363690_0b75586de3a3c2c86d821c115ddc0875e9e7bef3c20987be301e13b961259a25.pdf"
    content = Path(file_path).read_bytes()
    filename = Path(file_path).name
    
    print("=== PROCESSING CV ===")
    res = await process_cv_file(filename=filename, content=content, force_reprocess=True)
    print("STATUS:", res.get("status"))
    print("FULL NAME:", res.get("full_name"))
    print("EXTRACTED SKILLS:", res.get("skills"))
    print("DETERMINISTIC EXP:", res.get("deterministic_experience"))
    
    cv_key = "cv_1760363690_0b75586de3a3c2c86d821c115ddc0875e9e7bef3c20987be301e13b961259a25"
    
    print("\n=== RECOMMENDATION SERVICE OUTPUT ===")
    rec = RecommendationService.get_candidate_recommendations(cv_key)
    print(json.dumps(rec, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
