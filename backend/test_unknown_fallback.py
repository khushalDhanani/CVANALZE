import sys; sys.path.insert(0, "/Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend")
from app.services.job_taxonomy import TaxonomyClassifier

print(TaxonomyClassifier.are_families_compatible(["Production Team"], "Unknown"))
print(TaxonomyClassifier.are_families_compatible(["Production Team"], "Not Configured"))
