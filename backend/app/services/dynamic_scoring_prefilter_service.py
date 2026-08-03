# backend/app/services/dynamic_scoring_prefilter_service.py
import json
import logging
from typing import Any

from app.core.database import SessionLocal
from app.core.rule_config_manager import PrefilterRules, RuleConfigManager
from app.models.scoring_profile import ScoringProfileMaster, StopWord

logger = logging.getLogger("cv_analyzer")


class DynamicScoringAndPrefilterService:
    """
    Dynamic Prefilter Stop Words and Enterprise Scoring Profiles Service.
    Loads stop words, prefilter lexical weights, penalties, and thresholds from MSSQL
    with in-memory caching and graceful fallback to RuleConfigManager.
    """

    _stop_words_cache: set[str] | None = None
    _default_profile_cache: dict[str, Any] | None = None

    @classmethod
    def get_stop_words(cls) -> set[str]:
        if cls._stop_words_cache is None:
            cls.refresh_cache()
        return cls._stop_words_cache or set()

    @classmethod
    def get_prefilter_rules(cls) -> PrefilterRules:
        """Returns active PrefilterRules, merging MSSQL database rules if available."""
        rules = RuleConfigManager.get_prefilter_rules()
        sw = cls.get_stop_words()
        if sw:
            rules.stop_words = list(sw)
        return rules

    @classmethod
    def refresh_cache(cls) -> None:
        stop_words: set[str] = set()

        # 1. Load from MSSQL if available
        if SessionLocal is not None:
            try:
                with SessionLocal() as session:
                    db_words = session.query(StopWord.word).filter(StopWord.is_active == True).all()
                    stop_words.update(w[0].strip().lower() for w in db_words if w[0])

                    prof = (
                        session.query(ScoringProfileMaster)
                        .filter(
                            ScoringProfileMaster.is_default == True,
                            ScoringProfileMaster.is_active == True,
                        )
                        .first()
                    )
                    if prof:
                        cls._default_profile_cache = {
                            "lexical_weights": json.loads(prof.lexical_weights_json) if prof.lexical_weights_json else {},
                            "penalties": json.loads(prof.penalties_json) if prof.penalties_json else {},
                            "thresholds": json.loads(prof.thresholds_json) if prof.thresholds_json else {},
                        }
            except Exception as exc:
                logger.warning(f"[DYNAMIC_SCORING_PREFILTER] MSSQL query failed: {exc}")

        # 2. Merge fallback from rule_config.json
        try:
            config_rules = RuleConfigManager.get_prefilter_rules()
            if config_rules.stop_words:
                stop_words.update(w.strip().lower() for w in config_rules.stop_words if w)
        except Exception as exc:
            logger.warning(f"[DYNAMIC_SCORING_PREFILTER] RuleConfig fallback failed: {exc}")

        cls._stop_words_cache = stop_words
        logger.info(f"[DYNAMIC_SCORING_PREFILTER] Cache refreshed: {len(stop_words)} stop words loaded.")

    @classmethod
    def get_tenant_scoring_profile(cls, profile_code: str = "DEFAULT") -> dict[str, Any]:
        """
        Dynamically fetches scoring profile overrides (weights, penalties, thresholds)
        for a specific tenant or industry profile code from MSSQL.
        """
        if profile_code == "DEFAULT" and cls._default_profile_cache:
            return cls._default_profile_cache

        if SessionLocal is not None:
            try:
                with SessionLocal() as session:
                    prof = (
                        session.query(ScoringProfileMaster)
                        .filter(
                            ScoringProfileMaster.profile_code == profile_code.upper(),
                            ScoringProfileMaster.is_active == True,
                        )
                        .first()
                    )
                    if prof:
                        return {
                            "profile_code": prof.profile_code,
                            "profile_name": prof.profile_name,
                            "lexical_weights": json.loads(prof.lexical_weights_json) if prof.lexical_weights_json else {},
                            "penalties": json.loads(prof.penalties_json) if prof.penalties_json else {},
                            "thresholds": json.loads(prof.thresholds_json) if prof.thresholds_json else {},
                        }
            except Exception as exc:
                logger.warning(f"[DYNAMIC_SCORING_PREFILTER] Query failed for profile '{profile_code}': {exc}")

        # Fallback to default rule_config params
        match_cfg = RuleConfigManager.get_match_rules()
        prefilter_cfg = RuleConfigManager.get_prefilter_rules()
        return {
            "profile_code": "DEFAULT",
            "profile_name": "Default RuleConfig Profile",
            "lexical_weights": prefilter_cfg.lexical_weights.model_dump(),
            "penalties": match_cfg.cross_domain_guard.model_dump(),
            "thresholds": match_cfg.scoring_parameters.model_dump(),
        }
