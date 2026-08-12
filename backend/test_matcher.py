import re
from app.schemas.domain import KeywordConfig, MatchType

cv_text = """
    Sarah Developer
    Senior Full Stack & Mobile Engineer
    Skills: Flutter, Dart, React Native, REST APIs, Python, Git
    Experience: 4 years software development
"""
keywords = ["developer", "flutter", "dotnet", "full stack", "ui/ux", "desktop support", "software engineer", "machine learning"]

count = 0
for k in keywords:
    pattern = re.compile(r"(?:\b|_)" + re.escape(k) + r"(?:\b|_)", re.IGNORECASE)
    if pattern.search(cv_text):
        print("Matched:", k)
        count += 1
print("Total matches:", count)
