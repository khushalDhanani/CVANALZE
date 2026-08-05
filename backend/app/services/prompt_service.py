import string
from typing import Any, Optional, Set
from sqlalchemy.orm import Session

from app.core.cache import config_cache_manager
from app.core.database import PostgresAppSession
from app.models.prompts import PromptTemplateMaster
from app.core.config import settings
from app.core.error_handlers import PromptError
from app.core.logging import logger

class PromptService:
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
