import pytest
from tests.test_scale_benchmark import generate_synthetic_vacancies
from app.schemas.job_context import JobEvaluationContext
raw = generate_synthetic_vacancies(1)
j = JobEvaluationContext.from_jobs(raw)[0]
print("VAC_FAMILY:", j.vac_family)
