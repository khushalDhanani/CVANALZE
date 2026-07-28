import time
from unittest.mock import MagicMock

import pytest

from app.services.cv_service import scan_uploads_directory
from app.services.document_parser import DocumentParser


def test_document_parser_timeout(monkeypatch):
    def slow_parse(filename, content):
        time.sleep(1.5)
        return "slow content"

    monkeypatch.setattr(DocumentParser, "parse", slow_parse)

    with pytest.raises(TimeoutError, match="timed out"):
        DocumentParser.parse_with_timeout("slow.pdf", b"content", timeout_seconds=0.2)


def test_batch_processing_throttling_and_chunking(tmp_path, monkeypatch):
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

    start_time = time.time()
    results = scan_uploads_directory(
        uploads_dir=tmp_path,
        batch_size=2,
        max_workers=1,
        throttle_delay=0.3,
    )
    duration = time.time() - start_time

    assert len(results) == 3
    assert mock_process.call_count == 3
    # With 3 items and batch size 2, there are 2 chunks -> 1 throttle delay of 0.3s
    assert duration >= 0.25
