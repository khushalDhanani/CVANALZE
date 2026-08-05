import sys

with open('backend/app/services/scoring_engine.py', 'r') as f:
    content = f.read()

content = content.replace(
    'job_title="General Role",',
    'job_title="",'
)
content = content.replace(
    'department="General",',
    'department="",'
)

with open('backend/app/services/scoring_engine.py', 'w') as f:
    f.write(content)

