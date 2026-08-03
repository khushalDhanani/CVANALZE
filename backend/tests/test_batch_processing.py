import time

import pytest

from app.services.cv_service import scan_uploads_directory
from app.services.document_parser import MarkdownGenerator


def test_document_parser_timeout(monkeypatch):
    def slow_generate(filename, content):
        time.sleep(1.5)
        return "slow content"

    monkeypatch.setattr(MarkdownGenerator, "generate", slow_generate)

    with pytest.raises(TimeoutError, match="timed out"):
        MarkdownGenerator.generate_with_timeout("slow.pdf", b"content", timeout_seconds=0.2)


@pytest.mark.asyncio
async def test_batch_scan_returns_empty_for_missing_directory(tmp_path):
    missing_directory = tmp_path / "missing"

    result = await scan_uploads_directory(missing_directory)

    assert result == []
