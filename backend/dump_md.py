import sys
import json
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import DocumentStream
from io import BytesIO

def main():
    with open("uploads/Resume Abdul Mannan 1.pdf", "rb") as f:
        content = f.read()

    converter = DocumentConverter()
    doc_stream = DocumentStream(name="Resume Abdul Mannan 1.pdf", stream=BytesIO(content))
    doc = converter.convert(doc_stream).document
    
    with open("markdown_out.md", "w") as out:
        out.write(doc.export_to_markdown())
        
    with open("doc_dict.json", "w") as out:
        json.dump(doc.export_to_dict(), out, indent=2)

if __name__ == "__main__":
    main()
