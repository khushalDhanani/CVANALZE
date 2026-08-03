from unittest.mock import MagicMock

from app.core.config import settings
from app.services import document_conversion


def test_document_converter_initialization_is_lazy_and_reused(monkeypatch):
    converter = MagicMock()
    initializer = MagicMock(return_value=converter)
    monkeypatch.setattr(document_conversion, "_fast_converter_instance", None)
    monkeypatch.setattr(document_conversion, "_init_fast_converter", initializer)

    first = document_conversion._get_fast_converter()
    second = document_conversion._get_fast_converter()

    assert first is converter
    assert second is converter
    initializer.assert_called_once_with()


def test_document_parser_defaults_to_single_worker():
    assert settings.DOCUMENT_PARSER_WORKERS == 1
    assert settings.DOCUMENT_TABLE_STRUCTURE_ENABLED is True
    assert settings.PREFER_NATIVE_TEXT_EXTRACTION is False
    assert document_conversion._parser_thread_pool._max_workers == 1


def test_native_first_mode_skips_docling_for_text_rich_pdf(monkeypatch):
    native_text = "Candidate resume with sufficient native text. " * 5
    monkeypatch.setattr(settings, "PREFER_NATIVE_TEXT_EXTRACTION", True)
    monkeypatch.setattr(document_conversion.UploadService, "validate_content", MagicMock())
    monkeypatch.setattr(document_conversion, "_classify_pdf", MagicMock(return_value=("TEXT_PDF", native_text, len(native_text), False)))
    monkeypatch.setattr(document_conversion, "_get_pdf_page_count", MagicMock(return_value=2))
    converter = MagicMock(side_effect=AssertionError("Docling should not run for sufficient native text"))
    monkeypatch.setattr(document_conversion.DocumentConversionService, "_convert_fast", converter)

    result = document_conversion.DocumentConversionService.generate("resume.pdf", b"%PDF-lightweight-test")

    assert result.parser_used == "native_pdf"
    assert result.markdown == native_text.strip()
    assert result.page_count == 2
    converter.assert_not_called()
