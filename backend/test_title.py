import re
from app.services.resume_field_extractor import ResumeFieldExtractor
title_without_dates = "React.js Developer"
tokens = [token.lower() for token in re.split(r"[\s/\-&()]+", title_without_dates) if token]
print("tokens:", tokens)
keywords = ResumeFieldExtractor.JOB_TITLE_KEYWORDS
if not keywords:
    keywords = {
        "ENGINEER", "DEVELOPER", "MANAGER", "EXECUTIVE", "ANALYST", "OFFICER", "CONSULTANT", "DIRECTOR", 
        "LEAD", "SPECIALIST", "INSPECTOR", "ADMINISTRATOR", "TECHNICIAN", "INCHARGE", "IN CHARGE", 
        "OPERATOR", "ASSISTANT", "CHEMIST", "SCIENTIST", "PROGRAMMER", "ARCHITECT", "DESIGNER", 
        "COORDINATOR", "SUPERVISOR", "HEAD", "SR.", "JR.",
    }
matched = [token.upper() for token in tokens if token.upper() in keywords]
print("matched:", matched)
print("final result:", any(token.upper() in keywords for token in tokens))
