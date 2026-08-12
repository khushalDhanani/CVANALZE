from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from pydantic import BaseModel

from app.core.database import get_postgres_app_db
from app.core.logging import logger
from app.services.configuration_service import ConfigurationService
from app.services.system_rule_config_factory import SystemRuleConfigFactory
from app.core.rule_config_manager import UnifiedRuleConfig

router = APIRouter(prefix="/config", tags=["Configuration"])

class ActivateProfileRequest(BaseModel):
    tenant_id: str | None = None


@router.get("/schema")
async def get_rule_config_schema():
    """Expose the authoritative schema used by the structured configuration editor."""
    return ConfigurationService.get_editor_schema()


@router.get("/system-default")
async def get_system_default_rule_config():
    """Return one conservative, validated baseline for administrator review."""
    config = SystemRuleConfigFactory.build()
    ConfigurationService.validate_config(config)
    return config.model_dump(mode="json")


@router.get("/rules")
async def list_active_rules(
    tenant_id: str | None = None,
    db: Session = Depends(get_postgres_app_db),
):
    """List the active profile's normalized rules in deterministic groups."""
    inventory = ConfigurationService.list_active_rules(db=db, tenant_id=tenant_id)
    if not inventory:
        raise HTTPException(status_code=404, detail="No active configuration found.")
    return inventory


@router.post("/initialize")
async def initialize_rule_config(
    payload: UnifiedRuleConfig,
    request: Request,
    db: Session = Depends(get_postgres_app_db),
):
    """Create and activate the first complete global profile from structured options."""
    try:
        active = ConfigurationService.get_active_profile(db=db, tenant_id=None)
        if active:
            raise HTTPException(status_code=409, detail="An active global configuration already exists.")

        principal = getattr(request.state, "principal", None)
        audit_actor = principal.key_fingerprint if principal else None
        existing = ConfigurationService.get_profile(db=db, version_tag=payload.version, tenant_id=None)
        if existing:
            if existing.status != "DRAFT":
                raise HTTPException(status_code=409, detail="The requested configuration version already exists and is not a draft.")
            profile = existing
        else:
            profile = ConfigurationService.create_profile(
                db=db,
                version_tag=payload.version,
                config=payload,
                tenant_id=None,
                description=payload.description,
                created_by=audit_actor,
                audit_reason="Initial structured configuration setup",
            )

        activated = ConfigurationService.activate_profile(
            db=db,
            version_tag=profile.version_tag,
            tenant_id=None,
            activated_by=audit_actor,
            activation_reason="Initial structured configuration setup",
        )
        return {"status": "success", "activated_version": activated.version_tag, "tenant_id": None}
    except HTTPException:
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Configuration initialization conflicted with another request.") from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception(f"Failed to initialize rule configuration: {exc}")
        raise HTTPException(status_code=500, detail="Configuration initialization failed.") from exc



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
        from app.core.rule_config_manager import RuleConfigManager
        from app.core.error_handlers import SystemConfigurationError
        
        try:
            config = RuleConfigManager.get_config(tenant_id=tenant_id)
            return config.model_dump()
        except SystemConfigurationError:
            raise HTTPException(status_code=404, detail="No active configuration found.")
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(f"Failed to retrieve active config: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve configuration.") from exc
