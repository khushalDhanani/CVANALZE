from __future__ import annotations

import json
import string
from typing import Any, NamedTuple, Optional, Set

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from sqlalchemy.orm import Session

from app.core.cache import config_cache_manager
from app.core.database import PostgresAppSession
from app.core.error_handlers import PromptError
from app.core.logging import logger
from app.models.prompts import PromptTemplateMaster


class PromptReadiness(NamedTuple):
    ready: bool
    reason: str


class PromptService:
    OPTIMIZED_MATCH_PROMPT_NAME = "optimized_match"
    OPTIMIZED_MATCH_LANGUAGE = "en"
    OPTIMIZED_MATCH_ENVIRONMENT = "production"
    OPTIMIZED_MATCH_SCHEMA_ID = "cvai://prompts/optimized_match/response-schema/v1"
    OPTIMIZED_MATCH_PLACEHOLDERS = {"input_json", "domain_list_str", "dept_list_str"}
    OPTIMIZED_MATCH_SCHEMA_FIELDS = {
        "candidate_profile",
        "active_vacancy_summary",
        "ai_career_summary",
        "matched_vacancies",
    }

    @classmethod
    def get_prompt(
        cls,
        prompt_name: str,
        placeholders: dict[str, Any],
        tenant_id: Optional[str] = None,
        model: Optional[str] = None,
        target_schema: Optional[str] = None,
        language: str = "en",
        environment: str = "production"
    ) -> str:
        if prompt_name == cls.OPTIMIZED_MATCH_PROMPT_NAME:
            readiness = cls.check_required_optimized_match_prompt()
            if not readiness.ready:
                logger.error("Required optimized_match prompt is not ready: %s", readiness.reason)
                raise PromptError("PROMPT_UNAVAILABLE")
        cache_key = f"prompt_tmpl:{prompt_name}:{tenant_id or 'none'}:{model or 'none'}:{target_schema or 'none'}:{language}:{environment}"
        
        template = config_cache_manager.get(cache_key)
        
        if not template:
            template = cls._fetch_prompt_from_db(
                prompt_name, tenant_id, model, target_schema, language, environment
            )
            if template:
                config_cache_manager.set(cache_key, template)
                
        if not template:
            logger.error(f"Prompt template '{prompt_name}' not found in DB.")
            raise PromptError("PROMPT_UNAVAILABLE")
                
        try:
            return template.format(**placeholders)
        except KeyError as e:
            logger.error(f"Missing required placeholder {e} in prompt template '{prompt_name}'")
            raise PromptError(f"Missing required placeholder {e}")
            
    @classmethod
    def _fetch_prompt_from_db(
        cls,
        prompt_name: str,
        tenant_id: Optional[str],
        model: Optional[str],
        target_schema: Optional[str],
        language: str,
        environment: str
    ) -> Optional[str]:
        with PostgresAppSession() as db:
            query = db.query(PromptTemplateMaster).filter(
                PromptTemplateMaster.prompt_name == prompt_name,
                PromptTemplateMaster.is_active == True,
                PromptTemplateMaster.language == language,
                PromptTemplateMaster.environment == environment
            )
            if prompt_name == cls.OPTIMIZED_MATCH_PROMPT_NAME:
                from app.core.config import settings

                query = query.filter(PromptTemplateMaster.version_tag == settings.OPTIMIZED_PROMPT_VERSION)
            
            # 1. Exact match
            exact_match = query.filter(
                PromptTemplateMaster.tenant_id == tenant_id,
                PromptTemplateMaster.model == model,
                PromptTemplateMaster.target_schema == target_schema
            ).order_by(PromptTemplateMaster.version_tag.desc()).first()
            
            if exact_match:
                return exact_match.system_instruction
                
            # 2. Fallback to generic tenant, specific model & schema
            if tenant_id is not None:
                fallback_match_1 = query.filter(
                    PromptTemplateMaster.tenant_id.is_(None),
                    PromptTemplateMaster.model == model,
                    PromptTemplateMaster.target_schema == target_schema
                ).order_by(PromptTemplateMaster.version_tag.desc()).first()
                if fallback_match_1:
                    return fallback_match_1.system_instruction
                
            # 3. Ultimate fallback to generic (no tenant, no model, no schema)
            generic_match = query.filter(
                PromptTemplateMaster.tenant_id.is_(None),
                PromptTemplateMaster.model.is_(None),
                PromptTemplateMaster.target_schema.is_(None)
            ).order_by(PromptTemplateMaster.version_tag.desc()).first()
            
            if generic_match:
                return generic_match.system_instruction
                
            return None

    @classmethod
    def get_placeholders(cls, template: str) -> Set[str]:
        """Extract all format placeholders from the given template string."""
        return {fname for _, fname, _, _ in string.Formatter().parse(template) if fname}

    @classmethod
    def check_required_optimized_match_prompt(cls) -> PromptReadiness:
        """Validate the exact active prompt contract required by the CV worker."""
        from app.core.config import settings

        if PostgresAppSession is None:
            return PromptReadiness(False, "PostgreSQL prompt storage is not configured.")
        try:
            with PostgresAppSession() as db:
                prompt = (
                    db.query(PromptTemplateMaster)
                    .filter(
                        PromptTemplateMaster.prompt_name == cls.OPTIMIZED_MATCH_PROMPT_NAME,
                        PromptTemplateMaster.version_tag == settings.OPTIMIZED_PROMPT_VERSION,
                        PromptTemplateMaster.tenant_id.is_(None),
                        PromptTemplateMaster.model.is_(None),
                        PromptTemplateMaster.target_schema.is_(None),
                        PromptTemplateMaster.language == cls.OPTIMIZED_MATCH_LANGUAGE,
                        PromptTemplateMaster.environment == cls.OPTIMIZED_MATCH_ENVIRONMENT,
                        PromptTemplateMaster.is_active.is_(True),
                    )
                    .order_by(PromptTemplateMaster.prompt_id.desc())
                    .first()
                )
            if prompt is None:
                return PromptReadiness(False, f"Required active prompt version {settings.OPTIMIZED_PROMPT_VERSION} is unavailable.")
            missing_placeholders = cls.OPTIMIZED_MATCH_PLACEHOLDERS - cls.get_placeholders(prompt.system_instruction)
            if missing_placeholders:
                return PromptReadiness(False, "Required prompt placeholders are invalid.")
            try:
                schema = json.loads(prompt.expected_schema_json or "")
                Draft202012Validator.check_schema(schema)
            except (TypeError, ValueError, json.JSONDecodeError, SchemaError):
                return PromptReadiness(False, "Required prompt response schema is invalid.")
            required_fields = set(schema.get("required") or []) if isinstance(schema, dict) else set()
            schema_fields = set(schema.get("properties") or {}) if isinstance(schema, dict) else set()
            if (
                not isinstance(schema, dict)
                or schema.get("$id") != cls.OPTIMIZED_MATCH_SCHEMA_ID
                or schema.get("type") != "object"
                or not cls.OPTIMIZED_MATCH_SCHEMA_FIELDS.issubset(required_fields)
                or not cls.OPTIMIZED_MATCH_SCHEMA_FIELDS.issubset(schema_fields)
            ):
                return PromptReadiness(False, "Required prompt response schema is incompatible.")
            return PromptReadiness(True, "READY")
        except Exception as exc:
            logger.error("Could not validate required optimized_match prompt: %s", type(exc).__name__, exc_info=True)
            return PromptReadiness(False, "Required prompt validation is unavailable.")

    @classmethod
    def activate_prompt(
        cls,
        db: Session,
        prompt_id: int,
        required_placeholders: Set[str]
    ) -> PromptTemplateMaster:
        """
        Validates the prompt contains required placeholders and activates it,
        deactivating older versions for the same compatibility constraints.
        """
        prompt = db.query(PromptTemplateMaster).filter(PromptTemplateMaster.prompt_id == prompt_id).first()
        if not prompt:
            raise ValueError(f"Prompt {prompt_id} not found")
            
        found_placeholders = cls.get_placeholders(prompt.system_instruction)
        missing = required_placeholders - found_placeholders
        if missing:
            raise ValueError(f"Cannot activate prompt. Missing required placeholders: {missing}")
            
        db.query(PromptTemplateMaster).filter(
            PromptTemplateMaster.prompt_name == prompt.prompt_name,
            PromptTemplateMaster.tenant_id == prompt.tenant_id,
            PromptTemplateMaster.model == prompt.model,
            PromptTemplateMaster.target_schema == prompt.target_schema,
            PromptTemplateMaster.language == prompt.language,
            PromptTemplateMaster.environment == prompt.environment,
            PromptTemplateMaster.is_active == True
        ).update({"is_active": False})
        
        prompt.is_active = True
        db.commit()
        db.refresh(prompt)
        
        # Invalidate cache so that next request pulls the newly activated prompt
        config_cache_manager.delete_by_pattern(f"prompt_tmpl:{prompt.prompt_name}:*")
        
        return prompt
