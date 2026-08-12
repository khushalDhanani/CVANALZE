with open('tests/conftest.py', 'r') as f:
    content = f.read()

old_cis = """                keywords=["developer", "flutter", "dotnet", "full stack", "ui/ux", "desktop support", "software engineer", "machine learning"],"""
new_cis = """                keywords=["developer", "flutter", "dotnet", "full stack", "ui/ux", "desktop support", "software engineer", "machine learning", {"term": "IT", "match_type": "CASE_SENSITIVE_ACRONYM", "weight": 1.0}, "network", "server", "infrastructure"],"""

content = content.replace(old_cis, new_cis)

with open('tests/conftest.py', 'w') as f:
    f.write(content)
