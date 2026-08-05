import sys
import re

with open('backend/app/services/match_service.py', 'r') as f:
    content = f.read()

# Replace General fallbacks
content = content.replace(
    'recommended_dept = cand_profile.get("recommended_department", "General")',
    'recommended_dept = cand_profile.get("recommended_department", "")'
)
content = content.replace(
    'professional_domain = cand_profile.get("professional_domain", "General Operations")',
    'professional_domain = cand_profile.get("professional_domain", "")'
)
content = content.replace(
    'roles_str = ", ".join(suitable_roles) if suitable_roles else "General Roles"',
    'roles_str = ", ".join(suitable_roles) if suitable_roles else ""'
)

# Replace in _empty_job_match
content = content.replace(
    'job_title="General Role",',
    'job_title="",'
)
content = content.replace(
    'department="General",',
    'department="",'
)
content = content.replace(
    'department_name="General",',
    'department_name="",'
)

# And in analysis_single_cv
content = content.replace(
    'rec_dept = cand_profile.get("recommended_department", "General")',
    'rec_dept = cand_profile.get("recommended_department", "")'
)
content = content.replace(
    'prof_domain = cand_profile.get("professional_domain", "General Operations")',
    'prof_domain = cand_profile.get("professional_domain", "")'
)

with open('backend/app/services/match_service.py', 'w') as f:
    f.write(content)

