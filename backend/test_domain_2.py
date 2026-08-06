from pathlib import Path
import json
import asyncio

def main():
    from app.services.cv_service import process_cv_file

    file_path = "uploads/cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6.pdf"
    content = Path(file_path).read_bytes()
    filename = Path(file_path).name

    result = asyncio.run(process_cv_file(filename=filename, content=content, force_reprocess=True))
    resume_json = result.get("resume_json", {})
    print("KEYS:", resume_json.keys())
    if "work_experience" in resume_json:
        print("WORK EXP LEN:", len(resume_json["work_experience"]))
    if "projects" in resume_json:
        print("PROJECTS LEN:", len(resume_json["projects"]))
    if "experience" in resume_json:
        print("EXPERIENCE LEN:", len(resume_json["experience"]))
    
if __name__ == "__main__":
    main()
