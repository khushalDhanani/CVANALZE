with open('tests/test_domain_matching.py', 'r') as f:
    content = f.read()

test1 = """def test_short_acronym_pronoun_rejection():
    \"\"\"it was responsible for... -> does NOT imply Information Technology\"\"\"
    from app.services.job_taxonomy import TaxonomyClassifier, CandidateResumeDTO
    
    cv_text = "I am a plant assistant. it was responsible for doing the daily maintenance."
    dto = CandidateResumeDTO.from_resume(cv_text)
    
    classification = TaxonomyClassifier.classify_candidate_dto(dto)
    
    assert classification.domain != "Information Technology & Software"
    assert classification.domain in ("Unknown", "Industrial Maintenance", "Plant & Maintenance", "Engineering", "Operations", "Other")
"""

test2 = """def test_short_acronym_valid_acceptance():
    \"\"\"IT Support Engineer -> classifies as Information Technology\"\"\"
    from app.services.job_taxonomy import TaxonomyClassifier, CandidateResumeDTO
    
    cv_text = "IT Support Engineer handling all network and server infrastructure."
    dto = CandidateResumeDTO.from_resume(cv_text)
    
    classification = TaxonomyClassifier.classify_candidate_dto(dto)
    
    assert classification.domain == "Information Technology & Software"
"""

if "test_short_acronym_pronoun_rejection" not in content:
    content += "\n\n" + test1 + "\n" + test2

test3 = """def test_case_insensitive_lowercase_qa():
    cv_text = "manual qa engineer executing test cases. qa testing."
    from app.services.job_taxonomy import TaxonomyClassifier, CandidateResumeDTO
    dto = CandidateResumeDTO.from_resume(cv_text)
    classification = TaxonomyClassifier.classify_candidate_dto(dto)
    assert classification.domain == "Quality Assurance"
"""

if "test_case_insensitive_lowercase_qa" not in content:
    content += "\n" + test3

with open('tests/test_domain_matching.py', 'w') as f:
    f.write(content)
