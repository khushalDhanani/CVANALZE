import pytest
from app.services.job_taxonomy import TaxonomyClassifier, CandidateResumeDTO

def test_debug(mock_department_domain_repo):
    software_cv = """
    Sarah Developer
    Senior Full Stack & Mobile Engineer
    Skills: Flutter, Dart, React Native, REST APIs, Python, Git
    Experience: 4 years software development
    """
    dto = CandidateResumeDTO.from_resume(software_cv)
    print("RAW SKILLS:", dto.raw_skills)
    print("RAW SUMMARY:", repr(dto.raw_summary))
    print("EXP TEXT:", repr(" ".join(dto.raw_experience_titles)))
    
    cls = TaxonomyClassifier.classify_candidate_dto(dto)
    print("DOMAIN:", cls.domain)

    # Let's see what matches we get!
    from app.repositories.department_domain import department_domain_repository
    for matcher in department_domain_repository.get_domain_matchers():
        if matcher.domain.department_name == "CIS Team":
            print("MATCHES FOR EXP:", matcher.keyword_match_count(" ".join(dto.raw_experience_titles)))
            print("MATCHES FOR SUMMARY:", matcher.keyword_match_count(dto.raw_summary))
            print("MATCHES FOR SKILLS:", matcher.keyword_match_count(" ".join(dto.raw_skills)))
