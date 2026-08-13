import sys
sys.path.append('.')
from app.repositories.result import ResultRepository

cv_key = "cv_1764688095_CandidateCVFileName_13349"
res = ResultRepository.resolve_result(cv_key)
print("Resolved:", res.get("status") if res else "None")
