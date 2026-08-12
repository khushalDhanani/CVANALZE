import pytest

from app.core.error_handlers import DocumentExtractionTimeoutError
from app.services import document_conversion
from app.services.cv_service import scan_uploads_directory
from app.services.document_parser import MarkdownGenerator


def test_document_parser_timeout(monkeypatch):
    class FakeReceiver:
        def poll(self, _timeout=None):
            return False

        def close(self):
            pass

    class FakeSender:
        def close(self):
            pass

    class FakeProcess:
        def __init__(self):
            self.alive = True
            self.terminated = False

        def start(self):
            pass

        def is_alive(self):
            return self.alive

        def terminate(self):
            self.terminated = True
            self.alive = False

        def join(self, timeout=None):
            pass

        def close(self):
            pass

    process = FakeProcess()

    class FakeContext:
        @staticmethod
        def Pipe(duplex=False):
            return FakeReceiver(), FakeSender()

        @staticmethod
        def Process(**_kwargs):
            return process

    monkeypatch.setattr(document_conversion, "_parser_process_context", FakeContext())

    with pytest.raises(DocumentExtractionTimeoutError, match="timed out"):
        MarkdownGenerator.generate_with_timeout("slow.pdf", b"content", timeout_seconds=0.01)

    assert process.terminated is True


@pytest.mark.asyncio
async def test_batch_scan_returns_empty_for_missing_directory(tmp_path):
    missing_directory = tmp_path / "missing"

    result = await scan_uploads_directory(missing_directory)

    assert result == []
