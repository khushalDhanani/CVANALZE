import pytest
from io import BytesIO
from app.services.document_parser import MarkdownGenerator

def test_invalid_docx_structure_validation_error():
    """Verify that fake or corrupted .docx files fail structural validation with explicit 'Invalid Word document' message."""
    fake_docx_content = b"This is plain text pretending to be a docx file."
    
    with pytest.raises(ValueError) as exc_info:
        MarkdownGenerator.generate("corrupted_resume.docx", fake_docx_content)
    
    assert "Invalid Word document" in str(exc_info.value)
    assert "corrupted file or invalid archive" in str(exc_info.value)


def test_docx_missing_document_xml_error():
    """Verify that zip archives missing word/document.xml raise explicit 'Invalid Word document' error."""
    import zipfile

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("something_else.txt", "hello")
    buf.seek(0)
    fake_zip = buf.getvalue()

    with pytest.raises(ValueError) as exc_info:
        MarkdownGenerator.generate("missing_xml.docx", fake_zip)

    assert "Invalid Word document" in str(exc_info.value)
    assert "word/document.xml" in str(exc_info.value)
