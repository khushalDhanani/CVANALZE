import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

# Ensure backend root is in PYTHONPATH
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(backend_dir))

from app.repositories.job import JobRepository
from app.services.cv_service import process_cv_file
from app.services.document_parser import MarkdownResult

FIXTURES_DIR = backend_dir / "tests" / "fixtures"

async def test_candidate(name: str, fixture_file: str, cv_id: str):
    print("\n=========================================")
    print(f"Testing Candidate: {name} (Fixture: {fixture_file})")
    print("=========================================")
    
    fixture_path = FIXTURES_DIR / fixture_file
    with open(fixture_path, "r", encoding="utf-8") as f:
        cv_text = f.read()

    mock_extraction = MarkdownResult(
        markdown=cv_text,
        structured_doc={},
        page_count=1,
        is_scanned=False,
        ocr_applied=False
    )
    
    with patch("app.services.document_parser.MarkdownGenerator.parse", return_value=mock_extraction):
        # We pass the fixture text natively
        result = await process_cv_file(
            filename=f"{cv_id}_mock.md",
            content=cv_text.encode("utf-8"),
            cv_id=cv_id,
            force_reprocess=True
        )
        return result

async def run_tests():
    print("Fetching dynamic active vacancies...")
    openings = JobRepository.get_all_jobs()
    print(f"Loaded {len(openings)} vacancies.")
    
    # 1. Domain-Collision Case
    await test_candidate(
        "Domain-Collision (Flutter Tech Role)", 
        "domain_collision_flutter.md", 
        "fixture_flutter"
    )
    
    # 2. Skill-Specific Tech Case
    await test_candidate(
        "Skill-Specific (ASP.NET)", 
        "skill_specific_aspnet.md", 
        "fixture_aspnet"
    )
    
    # 3. False-100% / Empty-Requirements Case
    # Find an active vacancy with empty requirements
    empty_req_vid = None
    for job in openings:
        # Check if skills/quals are effectively empty strings or None
        skills = job.get("required_skills", [])
        quals = job.get("required_qualifications", [])
        if not skills and not quals:
            empty_req_vid = str(job.get("vacancy_id") or job.get("id"))
            print(f"Found dynamic empty-requirements vacancy: {empty_req_vid} ({job.get('job_title')})")
            break
            
    if empty_req_vid:
        await test_candidate(
            "Empty-Requirements", 
            "empty_requirements.md", 
            "fixture_empty"
        )
        print(f"Empty-requirements test completed. Please verify logs for vacancy {empty_req_vid}.")
    else:
        print("No active empty-requirements vacancy found in the live DB to test against.")
        
    print("\nRegression suite finished! Check the debug logs to confirm:")
    print(" - Flutter developer outranks plant/maintenance roles.")
    print(" - ASP.NET developer correctly matches Software Developer roles.")
    print(" - Empty-requirements vacancy does not artificially cap at 100%.")

if __name__ == "__main__":
    asyncio.run(run_tests())
