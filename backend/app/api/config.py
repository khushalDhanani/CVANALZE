from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import logger
from app.repositories.config import ConfigRepository
from app.schemas.config import MatchEngineConfigResponse, MatchEngineConfigUpdate
from app.services.configuration_service import ConfigurationService
from app.core.rule_config_manager import UnifiedRuleConfig

router = APIRouter(prefix="/config", tags=["Configuration"])

class ActivateProfileRequest(BaseModel):
    tenant_id: str | None = None

@router.get("/match", response_model=MatchEngineConfigResponse, deprecated=True)
async def get_match_config(db: Session = Depends(get_db)):
    """Retrieve the current matching engine configuration weights and thresholds."""
    try:
        return MatchEngineConfigResponse(
            MATCH_HIGH_THRESHOLD=float(ConfigRepository.get_setting("MATCH_HIGH_THRESHOLD", settings.MATCH_HIGH_THRESHOLD, db)),
            MATCH_MEDIUM_THRESHOLD=float(ConfigRepository.get_setting("MATCH_MEDIUM_THRESHOLD", settings.MATCH_MEDIUM_THRESHOLD, db)),
            MANDATORY_FAILURE_PENALTY_PER_ITEM=float(
                ConfigRepository.get_setting(
                    "MANDATORY_FAILURE_PENALTY_PER_ITEM",
                    settings.MANDATORY_FAILURE_PENALTY_PER_ITEM,
                    db,
                )
            ),
            MAX_SCORE_ON_MANDATORY_FAILURE=float(
                ConfigRepository.get_setting(
                    "MAX_SCORE_ON_MANDATORY_FAILURE",
                    settings.MAX_SCORE_ON_MANDATORY_FAILURE,
                    db,
                )
            ),
            LLM_SEMANTIC_WEIGHT=float(ConfigRepository.get_setting("LLM_SEMANTIC_WEIGHT", settings.LLM_SEMANTIC_WEIGHT, db)),
            MAX_LLM_BOOST=float(ConfigRepository.get_setting("MAX_LLM_BOOST", settings.MAX_LLM_BOOST, db)),
            LLM_SKIP_MARGIN_THRESHOLD=float(ConfigRepository.get_setting("LLM_SKIP_MARGIN_THRESHOLD", settings.LLM_SKIP_MARGIN_THRESHOLD, db)),
            LLM_SKIP_COVERAGE_THRESHOLD=float(
                ConfigRepository.get_setting(
                    "LLM_SKIP_COVERAGE_THRESHOLD",
                    settings.LLM_SKIP_COVERAGE_THRESHOLD,
                    db,
                )
            ),
            MATCH_COMPONENT_WEIGHTS=ConfigRepository.get_setting(
                "MATCH_COMPONENT_WEIGHTS",
                {
                    "role": 0.15,
                    "skills": 0.25,
                    "experience": 0.15,
                    "education": 0.10,
                    "domain": 0.15,
                    "technology": 0.10,
                    "certification": 0.05,
                    "responsibilities": 0.05,
                },
                db,
            ),
        )
    except Exception as exc:
        logger.exception(f"Failed to retrieve match config: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration.") from exc


@router.put("/match", response_model=MatchEngineConfigResponse, deprecated=True)
async def update_match_config(payload: MatchEngineConfigUpdate, db: Session = Depends(get_db)):
    """Update the matching engine configuration. Values are merged with existing settings."""
    try:
        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            ConfigRepository.update_setting(key, value, db)

        return await get_match_config(db)
    except Exception as exc:
        logger.exception(f"Failed to update match config: {exc}")
        raise HTTPException(status_code=500, detail="Failed to update configuration.") from exc


@router.post("/versions")
async def create_rule_config_version(
    payload: UnifiedRuleConfig,
    version_tag: str,
    tenant_id: str | None = None,
    description: str | None = None,
    created_by: str | None = None,
    audit_reason: str | None = None,
    db: Session = Depends(get_db),
):
    """Create a new unified rule configuration version."""
    try:
        profile = ConfigurationService.create_profile(
            db=db,
            version_tag=version_tag,
            config=payload,
            tenant_id=tenant_id,
            description=description,
            created_by=created_by,
            audit_reason=audit_reason,
        )
        return {"status": "success", "profile_id": profile.profile_id, "version_tag": profile.version_tag}
    except Exception as exc:
        logger.exception(f"Failed to create config version: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/versions/{version_tag}/activate")
async def activate_rule_config_version(
    version_tag: str,
    payload: ActivateProfileRequest,
    db: Session = Depends(get_db),
):
    """Activate a specific rule configuration version."""
    try:
        profile = ConfigurationService.activate_profile(
            db=db,
            version_tag=version_tag,
            tenant_id=payload.tenant_id,
        )
        return {"status": "success", "activated_version": profile.version_tag, "tenant_id": payload.tenant_id}
    except Exception as exc:
        logger.exception(f"Failed to activate config version: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/active")
async def get_active_rule_config(
    tenant_id: str | None = None,
    db: Session = Depends(get_db),
):
    """Retrieve the currently active unified rule configuration for a tenant."""
    try:
        profile = ConfigurationService.get_active_profile(db=db, tenant_id=tenant_id)
        if not profile:
            raise HTTPException(status_code=404, detail="No active configuration found.")
            
        import json
        return {
            "version": profile.version_tag,
            "description": profile.description,
            "global_confidence_tiers": json.loads(profile.global_confidence_tiers_json),
            "fields": json.loads(profile.fields_config_json),
            "scoring": json.loads(profile.scoring_rules_json),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to retrieve active config: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration.") from exc
