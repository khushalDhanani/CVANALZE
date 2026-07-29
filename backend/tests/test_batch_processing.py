import time
import pytest
from unittest.mock import MagicMock
from app.services.document_parser import DocumentParser


def test_document_parser_timeout(monkeypatch):
    def slow_parse(filename, content):
        time.sleep(1.5)
        return "slow content"

    monkeypatch.setattr(DocumentParser, "parse", slow_parse)

    with pytest.raises(TimeoutError, match="timed out"):
        DocumentParser.parse_with_timeout("slow.pdf", b"content", timeout_seconds=0.2)


@pytest.mark.asyncio
async def test_batch_processing_throttling_and_chunking(tmp_path, monkeypatch):
    dummy_pdf_1 = tmp_path / "resume_1.pdf"
    dummy_pdf_2 = tmp_path / "resume_2.pdf"
    dummy_pdf_3 = tmp_path / "resume_3.pdf"

    for f in [dummy_pdf_1, dummy_pdf_2, dummy_pdf_3]:
        f.write_bytes(b"%PDF-1.4 dummy content")

    mock_process = MagicMock(
        return_value={
            "characters": 100,
            "result_file_path": "uploads/results/mock.json",
            "match_analysis": {
                "best_match": {
                    "job_title": "Software Engineer",
                    "score": 85.0,
                    "classification": "HIGH",
                }
            },
        }
    )

    monkeypatch.setattr("app.services.cv_service.process_cv_file", mock_process)
    assert dummy_pdf_1.exists()
    assert dummy_pdf_2.exists()
    assert dummy_pdf_3.exists()
