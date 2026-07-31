import io
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.repositories.result import ResultRepository

def test_dual_upload_key_alignment_and_single_entry():
    """
    Verify that uploading an identical CV file via /api/cv/upload (fast-track)
    and /api/match/upload (enriched) produces the exact same cv_key, creates
    only 1 JSON file in RESULTS_DIR, and resolves to the exact same single repository entry.
    """
    client = TestClient(app)
    
    cv_filename = "dual_upload_test_resume.txt"
    cv_text_content = (
        b"Utkarsh Patil\n"
        b"Senior Software Developer\n"
        b"Email: utkarsh@example.com\n"
        b"Location: Vadodara, Gujarat\n"
        b"Skills: Python, FastAPI, React, Node.js, PostgreSQL, Docker\n"
        b"Experience: 6 years developing scalable web applications and REST APIs.\n"
    )

    # 1. Upload via /api/cv/upload
    resp1 = client.post("/api/cv/upload", files={"file": (cv_filename, cv_text_content, "text/plain")})
    assert resp1.status_code == 200, f"/api/cv/upload failed: {resp1.text}"
    key1 = resp1.json()["cv_key"]

    # 2. Upload via /api/match/upload
    resp2 = client.post("/api/match/upload", files={"file": (cv_filename, cv_text_content, "text/plain")})
    assert resp2.status_code == 200, f"/api/match/upload failed: {resp2.text}"
    key2 = resp2.json()["cv_key"]

    # 3. Key equality invariant
    assert key1 == key2 == "cv_dual_upload_test_resume", f"Key mismatch! key1='{key1}', key2='{key2}'"

    # 4. Result file count invariant
    json_files = list(settings.RESULTS_DIR.glob(f"*{Path(cv_filename).stem}*.json"))
    assert len(json_files) == 1, f"Expected exactly 1 JSON file, found {len(json_files)}: {[f.name for f in json_files]}"
    assert json_files[0].name == "cv_dual_upload_test_resume.json"

    # 5. Repository resolution invariant
    res1 = ResultRepository.read_result_by_filename(f"{key1}.json")
    res2 = ResultRepository.read_result_by_filename(f"{key2}.json")
    resolved = ResultRepository.resolve_result(key1)

    assert res1 is not None
    assert res2 is not None
    assert resolved is not None
    assert res1["scan_id"] == res2["scan_id"] == resolved["scan_id"] == "cv_dual_upload_test_resume"
