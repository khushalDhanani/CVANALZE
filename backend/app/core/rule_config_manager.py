import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger("cv_analyzer")

DEFAULT_CONFIG_PATH = Path(__file__).parent / "rule_config.json"


class GlobalTierBoundary(BaseModel):
    min_score: float = Field(..., ge=0.0, le=1.0)
    max_score: float = Field(..., ge=0.0, le=1.0)


class TierThresholds(BaseModel):
    high_min: float = Field(0.80, ge=0.0, le=1.0)
    medium_min: float = Field(0.50, ge=0.0, le=1.0)
    low_min: float = Field(0.00, ge=0.0, le=1.0)
    override_reason: Optional[str] = None


class DownstreamGates(BaseModel):
    min_acceptance_confidence: float = Field(0.50, ge=0.0, le=1.0)
    reject_email_fallback_as_unverified: bool = True
    max_word_count: Optional[int] = None
    max_char_length: Optional[int] = None
    require_gazetteer_for_high: Optional[bool] = None


class FieldRuleConfig(BaseModel):
    field_name: str
    description: str
    confidence_scoring: Dict[str, float]
    tier_thresholds: TierThresholds
    downstream_gates: DownstreamGates
    keywords: Dict[str, List[str]]

    def get_keyword_set(self, key: str) -> Set[str]:
        raw_list = self.keywords.get(key, [])
        return {item.lower().strip() for item in raw_list if item}

    def get_upper_keyword_set(self, key: str) -> Set[str]:
        raw_list = self.keywords.get(key, [])
        return {item.upper().strip() for item in raw_list if item}


class UnifiedRuleConfig(BaseModel):
    version: str
    description: str
    last_updated: str
    global_confidence_tiers: Dict[str, GlobalTierBoundary]
    fields: Dict[str, FieldRuleConfig]

    @model_validator(mode="after")
    def validate_safety_invariants(self) -> "UnifiedRuleConfig":
        global_high = self.global_confidence_tiers.get("HIGH", GlobalTierBoundary(min_score=0.80, max_score=1.00)).min_score
        global_medium = self.global_confidence_tiers.get("MEDIUM", GlobalTierBoundary(min_score=0.50, max_score=0.79)).min_score

        for field_name, field_cfg in self.fields.items():
            tier_t = field_cfg.tier_thresholds
            gate = field_cfg.downstream_gates.min_acceptance_confidence

            # Invariant 1: override_reason check if deviating from global tiers
            if (abs(tier_t.high_min - global_high) > 1e-4 or abs(tier_t.medium_min - global_medium) > 1e-4):
                if not tier_t.override_reason or not tier_t.override_reason.strip():
                    raise ValueError(
                        f"[SAFETY_GATE_VIOLATION] Field '{field_name}' tier thresholds "
                        f"(high_min={tier_t.high_min}, medium_min={tier_t.medium_min}) "
                        f"differ from global tiers (high={global_high}, medium={global_medium}) "
                        f"but override_reason is missing or empty."
                    )

            # Invariant 2: min_acceptance_confidence must be strictly > fallback score (0.30)
            email_fallback_score = field_cfg.confidence_scoring.get("email_username_fallback", 0.0)
            if email_fallback_score > 0.0 and gate <= email_fallback_score:
                raise ValueError(
                    f"[SAFETY_GATE_VIOLATION] Field '{field_name}' min_acceptance_confidence ({gate}) "
                    f"must be strictly greater than email_username_fallback score ({email_fallback_score})."
                )

            # Invariant 3: min_acceptance_confidence must always be >= medium_min for that same field
            if gate < tier_t.medium_min:
                raise ValueError(
                    f"[SAFETY_GATE_VIOLATION] min_acceptance_confidence ({gate}) cannot be lower than "
                    f"medium_min threshold ({tier_t.medium_min}) for field '{field_name}'"
                )

        return self


class RuleConfigManager:
    _active_config: Optional[UnifiedRuleConfig] = None
    _config_path: Path = DEFAULT_CONFIG_PATH

    @classmethod
    def load_config(
        cls,
        config_source: Optional[Dict[str, Any] | Path | str] = None,
    ) -> UnifiedRuleConfig:
        """Load, validate, and atomically activate a rule configuration."""
        if config_source is None:
            config_source = cls._config_path

        if isinstance(config_source, (str, Path)):
            path = Path(config_source)
            if not path.is_absolute():
                path = Path(__file__).parent / path
            with open(path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        elif isinstance(config_source, dict):
            raw_data = config_source
        else:
            raise ValueError(f"Invalid config_source type: {type(config_source)}")

        # 1. Pydantic Model & Safety Invariants Validation
        candidate_config = UnifiedRuleConfig.model_validate(raw_data)

        # 2. In-Memory Synthetic Smoke Test Suite
        cls._run_synthetic_smoke_tests(candidate_config)

        # 3. Atomic Swap
        cls._active_config = candidate_config
        logger.info(
            f"[RULE_CONFIG] Successfully loaded and activated rule_config "
            f"v{candidate_config.version} ({len(candidate_config.fields)} fields configured)"
        )
        return cls._active_config

    @classmethod
    def get_config(cls) -> UnifiedRuleConfig:
        if cls._active_config is None:
            cls.load_config()
        return cls._active_config

    @classmethod
    def get_field_config(cls, field_name: str) -> FieldRuleConfig:
        cfg = cls.get_config()
        if field_name not in cfg.fields:
            raise KeyError(f"Field '{field_name}' not configured in UnifiedRuleConfig")
        return cfg.fields[field_name]

    @classmethod
    def get_keywords(cls, field_name: str, key: str) -> Set[str]:
        field_cfg = cls.get_field_config(field_name)
        return field_cfg.get_keyword_set(key)

    @classmethod
    def get_upper_keywords(cls, field_name: str, key: str) -> Set[str]:
        field_cfg = cls.get_field_config(field_name)
        return field_cfg.get_upper_keyword_set(key)

    @classmethod
    def get_confidence_tier(cls, field_name: str, score: Optional[float]) -> str:
        if score is None or score <= 0.0:
            return "LOW"
        try:
            field_cfg = cls.get_field_config(field_name)
            tier_t = field_cfg.tier_thresholds
            if score >= tier_t.high_min:
                return "HIGH"
            elif score >= tier_t.medium_min:
                return "MEDIUM"
            else:
                return "LOW"
        except Exception:
            if score >= 0.80:
                return "HIGH"
            elif score >= 0.50:
                return "MEDIUM"
            else:
                return "LOW"

    @classmethod
    def _run_synthetic_smoke_tests(cls, candidate_config: UnifiedRuleConfig) -> None:
        """Execute in-memory synthetic smoke tests against candidate config before activation."""
        loc_cfg = candidate_config.fields.get("location")
        title_cfg = candidate_config.fields.get("job_title")
        comp_cfg = candidate_config.fields.get("company_name")

        if not loc_cfg or not title_cfg or not comp_cfg:
            return

        # Smoke Test 1: Location Null Suppression on Blacklisted Input
        blacklist = loc_cfg.get_keyword_set("blacklist")
        test_line = "Dear Sir, Madam"
        tokens = [t.lower() for t in re.split(r"[,\s]+", test_line) if t]
        if any(t in blacklist for t in tokens):
            loc_extracted = None
        else:
            loc_extracted = test_line
        if loc_extracted is not None:
            raise ValueError("[SMOKE_TEST_FAILURE] Failed to reject blacklisted location input 'Dear Sir, Madam'")

        # Smoke Test 2: Job Title Narrative Rejection
        starters = title_cfg.get_keyword_set("narrative_starters")
        phrases = title_cfg.get_keyword_set("narrative_phrases")
        test_title = "Graduated in 2020"
        title_tokens = [t.lower() for t in test_title.split()]
        if title_tokens[0] in starters or any(p in test_title.lower() for p in phrases):
            is_valid_title = False
        else:
            is_valid_title = True
        if is_valid_title is not False:
            raise ValueError("[SMOKE_TEST_FAILURE] Failed to reject narrative sentence 'Graduated in 2020' as job title")

        # Smoke Test 3: Company Name Header Rejection
        generic_headers = comp_cfg.get_keyword_set("generic_section_headers")
        test_header = "## Experience"
        clean_header = test_header.replace("#", "").strip().lower()
        if clean_header in generic_headers:
            is_valid_company = False
        else:
            is_valid_company = True
        if is_valid_company is not False:
            raise ValueError("[SMOKE_TEST_FAILURE] Failed to reject generic section header '## Experience' as company name")
