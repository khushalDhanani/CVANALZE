import pytest
from app.services.job_taxonomy import TaxonomyClassifier
from app.schemas.candidate_context import CandidateAnalysisContext

def test_manual():
    cand_domain, cand_families = TaxonomyClassifier.classify_candidate("Python developer")
    vac_domain, vac_family = TaxonomyClassifier.classify_vacancy({"title": "Software Engineer"})
    print(cand_domain, cand_families)
    print(vac_domain, vac_family)
    compat = TaxonomyClassifier.are_families_compatible(list(cand_families), vac_family)
    print("Compatible?", compat)

test_manual()
