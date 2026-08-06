import pytest
from app.services.candidate_domain_service import CandidateDomainService
from app.repositories.department_domain import DepartmentDomainRepository
repo = DepartmentDomainRepository(db_factory=lambda: None)

def loader(path):
    return [
        {
            "department_name": "Data & Analytics",
            "domain_name": "Data Science & Analytics",
            "keywords": ["machine learning"],
            "default_roles": ["Data Scientist"],
            "priority": 9,
            "is_active": True,
        }
    ]

# mock internal load
repo.get_all_domains = lambda: [
    type('obj', (object,), {'id': 1, 'department_name': 'Data & Analytics', 'domain_name': 'Data Science & Analytics', 'keywords': ['machine learning'], 'default_roles': ['Data Scientist'], 'priority': 9, 'is_active': True})()
]
repo.get_domain_matchers = lambda: [
    type('obj', (object,), {'keyword_match_count': lambda x: 1 if 'machine learning' in x.lower() else 0, 'domain': repo.get_all_domains()[0]})()
]

cv_text = """
Senior Data Scientist
Skills: Machine Learning
"""
profile = CandidateDomainService.extract_candidate_domain_profile(cv_text, domain_repository=repo)
print(profile)
