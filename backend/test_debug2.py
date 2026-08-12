import sys
sys.path.insert(0, '/Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend')
from app.services.job_taxonomy import TaxonomyClassifier, CandidateResumeDTO
from app.repositories.department_domain import department_domain_repository
cv_text = "IT Support Engineer handling all network and server infrastructure."
dto = CandidateResumeDTO.from_resume(cv_text)
for matcher in department_domain_repository.get_domain_matchers():
    m = matcher.keyword_match_count(dto.summary)
    if m > 0:
        print(f"{matcher.domain.domain_name}: {m} matches")
