from io import BytesIO

import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.main import app
from app.services.document_parser import DocumentParser


@pytest.fixture
def sample_docx_bytes() -> bytes:
    doc = Document()
    doc.add_heading("Alex Johnson", level=1)
    doc.add_paragraph("Email: alex.johnson@example.com | Phone: +1-555-0199")
    doc.add_heading("Skills", level=2)
    doc.add_paragraph("Python, FastAPI, SQL, Docker, Git")
    doc.add_heading("Experience", level=2)
    doc.add_paragraph("Senior Backend Engineer at TechCorp (2021 - Present)")
    doc.add_paragraph("Developed high-performance microservices and REST APIs.")
    doc.add_heading("Education", level=2)
    doc.add_paragraph("B.S. in Computer Science - University of Technology")

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_document_parser_extracts_docx(sample_docx_bytes: bytes):
    extraction = DocumentParser.parse("alex_johnson_cv.docx", sample_docx_bytes)

    assert len(extraction.markdown) > 0
    assert "Alex Johnson" in extraction.markdown
    assert "Skills" in extraction.markdown
    assert "Python" in extraction.markdown
    assert extraction.page_count >= 1
    assert isinstance(extraction.structured_doc, dict)


def test_document_parser_rejects_empty_file():
    with pytest.raises(ValueError, match="0 bytes"):
        DocumentParser.parse("empty.pdf", b"")


def test_document_parser_rejects_invalid_extension():
    with pytest.raises(ValueError, match="Unsupported file extension"):
        DocumentParser.parse("resume.txt", b"sample content")


def test_api_upload_cv_endpoint(sample_docx_bytes: bytes):
    client = TestClient(app)
    response = client.post(
        "/api/cv/upload",
        files={
            "file": (
                "alex_johnson_cv.docx",
                sample_docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["filename"] == "alex_johnson_cv.docx"
    assert data["characters"] > 0
    assert "Alex Johnson" in data["markdown"]
    assert "structured_doc" in data
    assert "match_analysis" in data
    assert data["result_file_path"].endswith(".json")


def test_api_upload_rejects_invalid_file_extension():
    client = TestClient(app)
    response = client.post(
        "/api/cv/upload",
        files={"file": ("invalid.txt", b"hello world", "text/plain")},
    )

    assert response.status_code == 400
    assert "Unsupported file extension" in response.json()["detail"]
