import sys
sys.path.insert(0, '/Users/khushaldhanani/Desktop/AETHERIND/cv-analyzer/backend')
import os
os.environ["ENV"] = "test"
from app.repositories.department_domain import department_domain_repository
print([d.domain.domain_name for d in department_domain_repository.get_domain_matchers()])
