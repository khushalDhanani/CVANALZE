from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.context_packer import pack_cv_context
from app.services.llm_input_security import sanitize_untrusted_text


@dataclass(frozen=True)
class EvaluationSummary:
    dataset_version: str
    total_cases: int
    passed_cases: int
    metrics: dict[str, float]

    @property
    def pass_rate(self) -> float:
        return self.passed_cases / self.total_cases if self.total_cases else 1.0


class ReliabilityEvaluationRunner:
    """Runs deterministic security/context gates without requiring a live local model."""

    @staticmethod
    def load_dataset(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def run(cls, path: Path) -> EvaluationSummary:
        dataset = cls.load_dataset(path)
        cases = dataset.get("cases", [])
        passed = 0
        injection_detected = 0
        deidentification_passed = 0
        context_retained = 0
        fairness_invariant = 0

        for case in cases:
            case_type = case.get("type")
            case_passed = False
            if case_type == "prompt_injection":
                detected = sanitize_untrusted_text(case.get("input", "")).injection_detected
                injection_detected += int(detected)
                case_passed = detected
            elif case_type == "deidentification":
                sanitized = sanitize_untrusted_text(case.get("input", ""), deidentify=True).text
                case_passed = all(forbidden.lower() not in sanitized.lower() for forbidden in case.get("forbidden", []))
                deidentification_passed += int(case_passed)
            elif case_type == "long_context":
                packed = pack_cv_context(case.get("input", ""), max_tokens=int(case.get("max_tokens", 128)), deidentify=True)
                case_passed = all(term.lower() in packed.text.lower() for term in case.get("required_terms", []))
                context_retained += int(case_passed)
            elif case_type == "fairness_counterfactual":
                left = sanitize_untrusted_text(case.get("left", ""), deidentify=True).text
                right = sanitize_untrusted_text(case.get("right", ""), deidentify=True).text
                case_passed = left == right
                fairness_invariant += int(case_passed)
            passed += int(case_passed)

        total = len(cases)
        return EvaluationSummary(
            dataset_version=str(dataset.get("version", "unknown")),
            total_cases=total,
            passed_cases=passed,
            metrics={
                "pass_rate": passed / total if total else 1.0,
                "injection_detection_count": float(injection_detected),
                "deidentification_pass_count": float(deidentification_passed),
                "long_context_retention_count": float(context_retained),
                "counterfactual_invariance_count": float(fairness_invariant),
            },
        )
