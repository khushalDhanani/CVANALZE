from app.services.job_taxonomy import TaxonomyClassifier, CandidateResumeDTO

cv_text = "manual qa engineer executing test cases. qa testing."
dto = CandidateResumeDTO.from_resume(cv_text)
classification = TaxonomyClassifier.classify_candidate_dto(dto)
print(f"Final domain: {classification.domain}")
print(f"Final rule: {classification.matched_rule}")
