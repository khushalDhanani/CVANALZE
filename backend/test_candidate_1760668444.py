import asyncio
import json
import logging
import uuid
from app.core.database import PostgresAppSession
from app.models.result import CVResult
from app.services.match_service import MatchService
from app.services.vacancy_prefilter import VacancyPreFilter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cv_analyzer")
logger.setLevel(logging.INFO)

async def run():
    with PostgresAppSession() as session:
        res = session.query(CVResult).filter(CVResult.cv_key == "cv_1760668444").first()
        cv_text = res.text_content
        rj = res.resume_json if isinstance(res.resume_json, dict) else json.loads(res.resume_json)
        ma = res.match_analysis if isinstance(res.match_analysis, dict) else json.loads(res.match_analysis)
        old_best_match = ma.get("best_match", {})
        old_domain = old_best_match.get("job_title", "None") if old_best_match else "None"

    result = await MatchService.analyze_single_cv(
        cv_text=cv_text,
        document_hash=str(uuid.uuid4()),
        resume_json=rj,
    )
    
    print("\n--- RESULTS ---")
    print(f"Before Domain: {old_domain}")
    print(f"After Domain (Best Match Title): {result.best_match.job_title if result.best_match else 'None'}")
    
    if result.best_match:
        print(f"Score: {result.best_match.score}")
        print("Acceptance Reason: Passed all mandatory requirements and scored highest.")
    else:
        print("Score: N/A")
        print("Rejection Reason: All vacancies rejected.")

    found_1215 = False
    for u in result.unsuitable_openings:
        if str(u.vacancy_id) == "1215":
            found_1215 = True
            print("\n1215 found in unsuitable! Reasons:")
            for f in u.mandatory_failures:
                print(" -", f.description, ":", f.reason)
            for m in u.score_impact.get("modifiers", []):
                print(" - Penalty:", m)

    if not found_1215 and not (result.best_match and str(result.best_match.vacancy_id) == "1215"):
        print("\n1215 NOT found anywhere!")
        
    if result.best_match and str(result.best_match.vacancy_id) == "1215":
        print("\n1215 is the BEST MATCH!")

asyncio.run(run())
