import pytest
from app.services.job_taxonomy import TaxonomyClassifier, CandidateResumeDTO
from app.repositories.department_domain import DepartmentDomainRepository

def test_debug(mock_department_domain_repo):
    software_cv = """
    Sarah Developer
    Senior Full Stack & Mobile Engineer
    Skills: Flutter, Dart, React Native, REST APIs, Python, Git
    Experience: 4 years software development
    """
    dto = CandidateResumeDTO.from_resume(software_cv)
    print("Skills:", dto.raw_skills)
    print("Summary:", dto.raw_summary)
    
    cls = TaxonomyClassifier.classify_candidate_dto(dto)
    print("Domain:", cls.domain)
    print("Family:", cls.job_family)

