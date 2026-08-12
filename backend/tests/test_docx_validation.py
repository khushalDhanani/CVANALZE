from io import BytesIO

import pytest

from app.services.document_parser import MarkdownGenerator


def test_invalid_docx_structure_validation_error():
    """Verify that fake or corrupted .docx files fail signature validation."""
    fake_docx_content = b"This is plain text pretending to be a docx file."

    with pytest.raises(ValueError) as exc_info:
        MarkdownGenerator.generate("corrupted_resume.docx", fake_docx_content)

    assert "Invalid DOCX signature" in str(exc_info.value)


def test_docx_missing_document_xml_error():
    """Verify that ZIP archives missing Office document entries are rejected."""
    import zipfile

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("something_else.txt", "hello")
    buf.seek(0)
    fake_zip = buf.getvalue()

    with pytest.raises(ValueError) as exc_info:
        MarkdownGenerator.generate("missing_xml.docx", fake_zip)

    assert "required Office entries are missing" in str(exc_info.value)
