from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.rule_config_manager import RuleConfigManager
from app.repositories.department_domain import department_domain_repository
from app.services.prompt_service import PromptService


@dataclass(frozen=True)
class MatchingReadiness:
    ready: bool
    reason_code: str = "READY"
    reason: str = "READY"


@dataclass
class MatchingQualityGate:
    """Fail-closed orchestration and audit lineage for the canonical matcher."""

    stages: dict[str, dict[str, Any]] = field(default_factory=dict)

    STAGE_NAMES = (
        "extraction_quality",
        "candidate_evidence_profile",
        "taxonomy_classification",
        "vacancy_retrieval",
        "mandatory_requirement_gate",
        "deterministic_fit_score",
        "llm_grounded_enrichment",
        "confidence_consistency_gate",
        "final_classification",
    )

    @classmethod
    def check_runtime_readiness(cls, *, has_vacancy_source: bool | None = None) -> MatchingReadiness:
        try:
            RuleConfigManager.get_config()
        except Exception:
            return MatchingReadiness(False, "RULE_CONFIG_UNAVAILABLE", "Required matching rule configuration is unavailable.")

        prompt = PromptService.check_required_optimized_match_prompt()
        if not prompt.ready:
            return MatchingReadiness(False, "PROMPT_UNAVAILABLE", prompt.reason)

        term_assets = RuleConfigManager.get_term_matching_assets()
        if not term_assets.get("noise_words") or not term_assets.get("aliases"):
            return MatchingReadiness(
                False,
                "RULE_CONFIG_INCOMPLETE",
                "Required term-matching noise words and governed aliases are not configured.",
            )

        if not department_domain_repository.is_ready():
            return MatchingReadiness(False, "TAXONOMY_UNAVAILABLE", "Required taxonomy/domain configuration contains zero active domains.")

        if has_vacancy_source is False:
            return MatchingReadiness(False, "VACANCY_SOURCE_UNAVAILABLE", "The active vacancy source is unavailable or empty.")
        return MatchingReadiness(True)

    def record(self, stage: str, status: str, **details: Any) -> None:
        if stage not in self.STAGE_NAMES:
            raise ValueError(f"Unknown matching quality gate stage: {stage}")
        self.stages[stage] = {"status": status, **details}

    def as_dict(self) -> dict[str, Any]:
        return {stage: self.stages.get(stage, {"status": "NOT_RUN"}) for stage in self.STAGE_NAMES}
