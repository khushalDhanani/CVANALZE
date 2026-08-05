from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pydantic import BaseModel

from app.core.config import settings
from app.core.database import get_postgres_app_db
from app.core.logging import logger
from app.repositories.config import ConfigRepository
from app.repositories.config import ConfigRepository
from app.services.configuration_service import ConfigurationService
from app.core.rule_config_manager import UnifiedRuleConfig

router = APIRouter(prefix="/config", tags=["Configuration"])

class ActivateProfileRequest(BaseModel):
    tenant_id: str | None = None



@router.post("/versions")
async def create_rule_config_version(
    payload: UnifiedRuleConfig,
    version_tag: str,
    tenant_id: str | None = None,
    description: str | None = None,
    created_by: str | None = None,
    audit_reason: str | None = None,
    db: Session = Depends(get_postgres_app_db),
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
    db: Session = Depends(get_postgres_app_db),
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
    db: Session = Depends(get_postgres_app_db),
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
