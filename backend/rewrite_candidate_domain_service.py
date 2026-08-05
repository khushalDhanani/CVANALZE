import sys

with open('backend/app/services/candidate_domain_service.py', 'r') as f:
    content = f.read()

content = content.replace(
    'prof_domain = dyn_res.industry_domain or dyn_res.db_department_name or "General Operations"',
    'prof_domain = dyn_res.industry_domain or dyn_res.db_department_name or ""'
)

with open('backend/app/services/candidate_domain_service.py', 'w') as f:
    f.write(content)
