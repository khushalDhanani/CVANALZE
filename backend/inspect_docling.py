import json
import sys
from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import DocumentStream
from io import BytesIO

def main():
    with open("uploads/ut1765894215_.pdf", "rb") as f:
        content = f.read()

    converter = DocumentConverter()
    doc_stream = DocumentStream(name="ut1765894215_.pdf", stream=BytesIO(content))
    doc = converter.convert(doc_stream).document
    d = doc.export_to_dict()
    
    with open("doc_dict.json", "w") as out:
        json.dump(d, out, indent=2)
        
    print(f"Exported to doc_dict.json. Top level keys: {list(d.keys())}")

if __name__ == "__main__":
    main()
