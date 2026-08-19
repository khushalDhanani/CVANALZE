from __future__ import annotations

import io
from pathlib import Path
import pytest
from app.core.config import settings
from app.services.upload_service import (
    NormalizedFilename,
    UploadService,
    UploadValidationError,
)
from app.services.resume_field_extractor import ResumeFieldExtractor
from app.schemas.contracts import ProcessingJobRecord, JobState


def test_normalize_filename_preserves_unicode_original_and_generates_safe_ascii():
    normalized = UploadService.normalize_filename("   ../../José Müller - Senior SRE (2026)!!.PDF   ")

    assert normalized.original_filename == "José Müller - Senior SRE (2026)!!.PDF"
    assert normalized.safe_filename == "Jose_Muller_-_Senior_SRE_2026.pdf"
    assert normalized.extension == "pdf"
    assert normalized.display_filename == "José Müller - Senior SRE (2026)!!.PDF"


def test_normalize_filename_strips_null_bytes_and_path_traversal():
    normalized = UploadService.normalize_filename("..\\..\\nested/dir/Candidate_CV\x00_test.docx")

    assert "\x00" not in normalized.original_filename
    assert "/" not in normalized.original_filename
    assert "\\" not in normalized.original_filename
    assert normalized.safe_filename == "Candidate_CV_test.docx"
    assert normalized.extension == "docx"


def test_synthetic_storage_pattern_detected_and_assigned_clean_display():
    raw_synthetic = "1761533883_CandidateCVFileName_13672.pdf"
    normalized = UploadService.normalize_filename(raw_synthetic)

    assert normalized.original_filename == "1761533883_CandidateCVFileName_13672.pdf"
    assert normalized.safe_filename == "1761533883_CandidateCVFileName_13672.pdf"
    assert normalized.display_filename == "Candidate_CV.pdf"


def test_windows_reserved_device_names_are_prefixed():
    con_normalized = UploadService.normalize_filename("CON.pdf")
    assert con_normalized.safe_filename == "doc_CON.pdf"

    nul_normalized = UploadService.normalize_filename("NUL.docx")
    assert nul_normalized.safe_filename == "doc_NUL.docx"


def test_long_filename_truncated_safely_preserving_extension():
    long_name = ("a" * 300) + ".pdf"
    normalized = UploadService.normalize_filename(long_name)

    assert len(normalized.safe_filename) <= settings.UPLOAD_FILENAME_MAX_CHARS
    assert normalized.safe_filename.endswith(".pdf")
    assert normalized.extension == "pdf"


def test_missing_and_empty_filename_rejected():
    with pytest.raises(UploadValidationError, match="Filename is required"):
        UploadService.normalize_filename("")

    with pytest.raises(UploadValidationError, match="Filename is required"):
        UploadService.normalize_filename(None)


def test_resume_field_extractor_rejects_synthetic_tokens():
    # Synthetic MSSQL column name & timestamp pattern should NOT yield candidate name
    assert ResumeFieldExtractor._name_from_filename("1761533883_CandidateCVFileName_13672.pdf") is None
    assert ResumeFieldExtractor._name_from_filename("cv_1761533883_CandidateCVFileName_13672.pdf") is None
    assert ResumeFieldExtractor._name_from_filename("CandidateCVFileName.pdf") is None
    assert ResumeFieldExtractor._name_from_filename("CandidatePhotoFileName.docx") is None
    assert ResumeFieldExtractor._name_from_filename("resume.pdf") is None
    assert ResumeFieldExtractor._name_from_filename("cv.pdf") is None

    # Legitimate person filename should yield capitalized candidate name
    assert ResumeFieldExtractor._name_from_filename("john_doe_cv.pdf") == "John Doe"
    assert ResumeFieldExtractor._name_from_filename("Jane-Smith-Resume-2026.docx") == "Jane Smith"


def test_processing_job_record_preserves_four_tier_filenames():
    record = ProcessingJobRecord(
        job_id="cvjob_12345",
        cv_key="cv_candidate_13672",
        content_hash="d41d8cd98f00b204e9800998ecf8427e",
        filename="John_Doe_CV.pdf",
        original_filename="John Doe - CV (2026).pdf",
        display_filename="John Doe - CV (2026).pdf",
        storage_filename="cv_candidate_13672_d41d8cd98f00b204.pdf",
        parser_version="1.0.0",
        schema_version="1.0.0",
        state=JobState.QUEUED,
    )

    assert record.original_filename == "John Doe - CV (2026).pdf"
    assert record.display_filename == "John Doe - CV (2026).pdf"
    assert record.filename == "John_Doe_CV.pdf"
    assert record.storage_filename == "cv_candidate_13672_d41d8cd98f00b204.pdf"
