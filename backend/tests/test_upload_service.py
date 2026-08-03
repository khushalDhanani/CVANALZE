from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import fitz
import pytest
from docx import Document
from fastapi import BackgroundTasks, HTTPException, UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from app.core.config import settings
from app.main import app
from app.services.upload_service import (
    UploadService,
    UploadTooLargeError,
    UploadValidationError,
)


def _pdf_bytes(page_count: int = 1) -> bytes:
    document = fitz.open()
    for _ in range(page_count):
        page = document.new_page()
        page.insert_text((72, 72), "Secure CV upload test")
    content = document.tobytes()
    document.close()
    return content


def _docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("Secure CV upload test")
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def _upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


def _scanned_pdf_bytes() -> bytes:
    document = fitz.open()
    page = document.new_page()
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 32, 32), False)
    pixmap.clear_with(255)
    page.insert_image(page.rect, stream=pixmap.tobytes("png"))
    content = document.tobytes()
    document.close()
    return content


def test_normalize_filename_removes_paths_unicode_and_unsafe_characters():
    normalized = UploadService.normalize_filename("../../Résumé (Final)!!.PDF")

    assert normalized.safe_filename == "Resume_Final.pdf"
    assert normalized.extension == "pdf"


@pytest.mark.asyncio
async def test_bounded_reader_raises_413_before_validation(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 8)
    monkeypatch.setattr(settings, "UPLOAD_READ_CHUNK_SIZE_BYTES", 3)

    with pytest.raises(UploadTooLargeError) as exc_info:
        await UploadService.accept_and_persist(
            _upload("resume.pdf", b"123456789", "application/pdf"),
            storage_key="cv_resume",
        )

    assert exc_info.value.status_code == 413
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_empty_upload_is_rejected_before_disk_write(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path)

    with pytest.raises(UploadValidationError, match="empty") as exc_info:
        await UploadService.accept_and_persist(
            _upload("resume.pdf", b"", "application/pdf"),
            storage_key="cv_resume",
        )

    assert exc_info.value.code == "empty_upload"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_valid_upload_is_persisted_atomically_with_server_name(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path)
    accepted = await UploadService.accept_and_persist(
        _upload("../Candidate CV.pdf", _pdf_bytes(), "application/pdf"),
        storage_key="cv_candidate_cv",
    )

    assert accepted.safe_filename == "Candidate_CV.pdf"
    assert accepted.storage_filename.startswith("cv_candidate_cv_")
    assert accepted.path == tmp_path.resolve() / accepted.storage_filename
    assert accepted.path.read_bytes() == accepted.content
    assert not list(tmp_path.glob(".upload-*.tmp"))


@pytest.mark.asyncio
async def test_invalid_signature_is_rejected_before_disk_write(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path)

    with pytest.raises(UploadValidationError, match="Invalid PDF signature"):
        await UploadService.accept_and_persist(
            _upload("resume.pdf", b"plain text", "application/pdf"),
            storage_key="cv_resume",
        )

    assert list(tmp_path.iterdir()) == []


def test_declared_mime_must_match_extension():
    with pytest.raises(UploadValidationError, match="Declared MIME type") as exc_info:
        UploadService.validate_content("resume.pdf", _pdf_bytes(), "text/plain")

    assert exc_info.value.code == "mime_type_mismatch"


def test_pdf_page_limit_is_configurable(monkeypatch):
    monkeypatch.setattr(settings, "MAX_PDF_PAGES", 1)

    with pytest.raises(UploadValidationError, match="page count") as exc_info:
        UploadService.validate_content("resume.pdf", _pdf_bytes(page_count=2), "application/pdf")

    assert exc_info.value.code == "pdf_page_limit_exceeded"


def test_damaged_pdf_structure_is_rejected():
    damaged_pdf = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog"

    with pytest.raises(UploadValidationError) as exc_info:
        UploadService.validate_content("resume.pdf", damaged_pdf, "application/pdf")

    assert exc_info.value.code in {"signature_mismatch", "invalid_document_structure"}


def test_scanned_pdf_structure_is_accepted_and_classified():
    from app.services.document_conversion import _classify_pdf

    scanned_pdf = _scanned_pdf_bytes()

    assert UploadService.validate_content("resume.pdf", scanned_pdf, "application/pdf") == "application/pdf"
    pdf_type, native_text, _character_count, has_images = _classify_pdf(scanned_pdf)
    assert pdf_type == "SCANNED_PDF"
    assert native_text == ""
    assert has_images is True


def test_docx_entry_limit_is_configurable(monkeypatch):
    monkeypatch.setattr(settings, "MAX_DOCX_ENTRIES", 1)

    with pytest.raises(UploadValidationError, match="entry count") as exc_info:
        UploadService.validate_content(
            "resume.docx",
            _docx_bytes(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    assert exc_info.value.code == "docx_entry_limit_exceeded"


def test_docx_expanded_size_limit_is_configurable(monkeypatch):
    monkeypatch.setattr(settings, "MAX_DOCX_EXPANDED_SIZE_BYTES", 1)

    with pytest.raises(UploadValidationError, match="expanded size") as exc_info:
        UploadService.validate_content("resume.docx", _docx_bytes())

    assert exc_info.value.code == "docx_expanded_size_exceeded"


def test_docx_zip_bomb_compression_ratio_is_rejected(monkeypatch):
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "A" * 10_000)
        archive.writestr("_rels/.rels", "rels")
        archive.writestr("word/document.xml", "document")
    monkeypatch.setattr(settings, "MAX_DOCX_COMPRESSION_RATIO", 2.0)

    with pytest.raises(UploadValidationError, match="compression ratio") as exc_info:
        UploadService.validate_content("resume.docx", output.getvalue())

    assert exc_info.value.code == "docx_compression_ratio_exceeded"


@pytest.mark.asyncio
async def test_failure_cleanup_policy_can_remove_retained_raw_file(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(settings, "RAW_UPLOAD_DELETE_ON_FAILURE", True)
    accepted = await UploadService.accept_and_persist(
        _upload("resume.pdf", _pdf_bytes(), "application/pdf"),
        storage_key="cv_resume",
    )

    UploadService.cleanup_after_processing(accepted.storage_filename, succeeded=False)

    assert not accepted.path.exists()


@pytest.mark.parametrize("filename", ["resume.doc", "resume.txt"])
def test_legacy_doc_and_txt_formats_are_rejected(filename):
    with pytest.raises(UploadValidationError, match="Unsupported file extension"):
        UploadService.validate_content(filename, b"not supported")


def test_both_upload_routes_return_413_and_write_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOADS_DIR", tmp_path)
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 8)
    monkeypatch.setattr(settings, "UPLOAD_READ_CHUNK_SIZE_BYTES", 3)
    client = TestClient(app)

    for route in ("/api/cv/upload", "/api/match/upload"):
        response = client.post(
            route,
            files={"file": ("resume.pdf", b"123456789", "application/pdf")},
        )
        assert response.status_code == 413
        assert "configured limit" in response.json()["detail"]

    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_reprocess_missing_raw_returns_409_without_deleting_result(monkeypatch, tmp_path):
    from app.api.candidates import reprocess_candidate
    from app.core.cache import CacheInvalidator, cv_result_cache_manager
    from app.repositories.result import ResultRepository

    uploads_dir = tmp_path / "uploads"
    results_dir = tmp_path / "results"
    uploads_dir.mkdir()
    results_dir.mkdir()
    result_path = results_dir / "cv_resume.json"
    result_path.write_text('{"id":"cv_resume"}', encoding="utf-8")
    existing_result = {
        "id": "cv_resume",
        "scan_id": "cv_resume",
        "filename": "resume.pdf",
        "cv_hash": "source-hash",
        "status": "COMPLETED",
    }
    monkeypatch.setattr(settings, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(settings, "RESULTS_DIR", results_dir)
    monkeypatch.setattr(ResultRepository, "read_result_by_filename", lambda _: existing_result)
    invalidated: list[str] = []
    deleted: list[str] = []
    monkeypatch.setattr(CacheInvalidator, "invalidate_cv", lambda value: invalidated.append(value))
    monkeypatch.setattr(cv_result_cache_manager, "delete", lambda value: deleted.append(value))
    monkeypatch.setattr(
        cv_result_cache_manager,
        "delete_by_pattern",
        lambda value: deleted.append(value),
    )

    with pytest.raises(HTTPException) as exc_info:
        await reprocess_candidate("cv_resume", BackgroundTasks())

    assert exc_info.value.status_code == 409
    assert result_path.exists()
    assert invalidated == []
    assert deleted == []
