import json
import fitz
from app.services.resume_field_extractor import ResumeFieldExtractor
doc = fitz.open('uploads/cv_Shruti_Dhameliya_React_js_Developer_3_Years_of_Exp_f13a7563d127d3a38a427b7b72125f041df1851c9992f6de07a9eca4bc1fbe57.pdf')
text = ""
for page in doc: text += page.get_text()

sections = ResumeFieldExtractor._split_sections(text.splitlines())
exp_lines = sections.get("experience", [])
extracted_exp = ResumeFieldExtractor._extract_employment(exp_lines)

for j in extracted_exp:
    print(f"Title: {j.get('job_title')} | Company: {j.get('company')} | Dates: {j.get('dates')}")
