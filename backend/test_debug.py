import sys
sys.path.insert(0, '/Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend')
from app.services.job_taxonomy import TaxonomyClassifier, CandidateResumeDTO
from app.repositories.department_domain import department_domain_repository
from app.core.rule_config_manager import RuleConfigManager
cv_text = "IT Support Engineer handling all network and server infrastructure."
dto = CandidateResumeDTO.from_resume(cv_text)
print("summary=", dto.summary)
print("matches IT?", department_domain_repository.get_domain_matchers()[8].keyword_match_count(dto.summary))
c = TaxonomyClassifier.classify_candidate_dto(dto)
print("Classification:", c)
