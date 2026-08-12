import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.evaluation.reliability_runner import ReliabilityEvaluationRunner


if __name__ == "__main__":
    dataset = Path(__file__).resolve().parents[1] / "app" / "data" / "evaluations" / "llm_reliability_v1.json"
    summary = ReliabilityEvaluationRunner.run(dataset)
    print(
        {
            "dataset_version": summary.dataset_version,
            "total_cases": summary.total_cases,
            "passed_cases": summary.passed_cases,
            "pass_rate": summary.pass_rate,
            "metrics": summary.metrics,
        }
    )
    raise SystemExit(0 if summary.pass_rate == 1.0 else 1)
