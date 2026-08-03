from io import BytesIO
from unittest.mock import patch

from docx import Document
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_dual_upload_key_alignment_and_single_raw_file(monkeypatch, tmp_path):
    """
    Verify that uploading an identical CV file via /api/cv/upload (fast-track)
    and /api/match/upload (enriched) produces the exact same cv_key, creates
    only one server-named raw upload because content-addressed storage is shared.
    """
    client = TestClient(app)
    
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path)
    cv_filename = "dual_upload_test_resume.docx"
    document = Document()
    document.add_paragraph("Utkarsh Patil - Senior Software Developer")
    output = BytesIO()
    document.save(output)
    cv_content = output.getvalue()
    content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    with patch("app.api.cv.background_process_cv"), patch("app.api.analysis.background_upload_and_analyze"):
        resp1 = client.post("/api/cv/upload", files={"file": (cv_filename, cv_content, content_type)})
        assert resp1.status_code == 200, f"/api/cv/upload failed: {resp1.text}"
        key1 = resp1.json()["cv_key"]

        resp2 = client.post("/api/match/upload", files={"file": (cv_filename, cv_content, content_type)})
        assert resp2.status_code == 200, f"/api/match/upload failed: {resp2.text}"
        key2 = resp2.json()["cv_key"]

    # 3. Key equality invariant
    assert key1 == key2 == "cv_dual_upload_test_resume", f"Key mismatch! key1='{key1}', key2='{key2}'"

    raw_files = list(tmp_path.glob("cv_dual_upload_test_resume_*.docx"))
    assert len(raw_files) == 1
    assert raw_files[0].read_bytes() == cv_content
