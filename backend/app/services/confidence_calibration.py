from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import settings


@dataclass(frozen=True)
class CalibratedConfidence:
    score: float
    review_recommended: bool
    factors: dict[str, float]
    calibration_version: str


class ConfidenceCalibrationService:
    """Evidence-derived baseline that can later be fit with isotonic calibration data."""

    @staticmethod
    def calculate(
        *,
        evidence_coverage: float,
        grounding_ratio: float,
        rule_llm_agreement: float,
        source_freshness: float = 1.0,
        extraction_quality: float = 1.0,
        validation_passed: bool = True,
    ) -> CalibratedConfidence:
        factors = {
            "evidence_coverage": _clamp(evidence_coverage),
            "grounding_ratio": _clamp(grounding_ratio),
            "rule_llm_agreement": _clamp(rule_llm_agreement),
            "source_freshness": _clamp(source_freshness),
            "extraction_quality": _clamp(extraction_quality),
        }
        raw_score = (
            factors["evidence_coverage"] * 0.30
            + factors["grounding_ratio"] * 0.30
            + factors["rule_llm_agreement"] * 0.20
            + factors["source_freshness"] * 0.10
            + factors["extraction_quality"] * 0.10
        )
        if not validation_passed:
            raw_score = min(raw_score, 0.35)
        calibration = _load_calibration(str(settings.LLM_CONFIDENCE_CALIBRATION_PATH))
        score = round(_apply_isotonic_curve(_clamp(raw_score), calibration["points"]), 4)
        return CalibratedConfidence(
            score=score,
            review_recommended=score < 0.6,
            factors=factors,
            calibration_version=calibration["version"],
        )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@lru_cache(maxsize=4)
def _load_calibration(path_value: str) -> dict[str, object]:
    path = Path(path_value)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        points = [(float(point[0]), float(point[1])) for point in payload["points"]]
        if len(points) >= 2 and points == sorted(points):
            return {"version": str(payload.get("version", "unknown")), "points": points}
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        pass
    return {"version": "identity-fallback", "points": [(0.0, 0.0), (1.0, 1.0)]}


def _apply_isotonic_curve(score: float, points: object) -> float:
    curve = list(points) if isinstance(points, list) else [(0.0, 0.0), (1.0, 1.0)]
    if score <= curve[0][0]:
        return _clamp(curve[0][1])
    for left, right in zip(curve, curve[1:]):
        if score <= right[0]:
            width = right[0] - left[0]
            ratio = (score - left[0]) / width if width else 0.0
            return _clamp(left[1] + (right[1] - left[1]) * ratio)
    return _clamp(curve[-1][1])
