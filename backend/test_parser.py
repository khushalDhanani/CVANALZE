import sys
import json
from app.services.document_parser import MarkdownGenerator

def main():
    with open("uploads/Resume Abdul Mannan 1.pdf", "rb") as f:
        content = f.read()

    result = MarkdownGenerator.generate("Resume Abdul Mannan 1.pdf", content)
    
    with open("debug_sanitized.md", "w") as f:
        f.write(result.markdown)
        
    print("Wrote debug_sanitized.md")
    print("----- EXTRACTED JSON -----")
    print(json.dumps(result.resume_json, indent=2))

if __name__ == "__main__":
    main()
