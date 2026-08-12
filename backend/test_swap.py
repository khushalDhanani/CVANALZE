from app.services.resume_field_extractor import ResumeFieldExtractor
current = {"company": "Braincuber Technology", "job_title": "React.js Developer"}
ResumeFieldExtractor._fix_company_title_swap(current)
print(current)
