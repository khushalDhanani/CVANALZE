from __future__ import annotations

import hashlib
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


class ResolvedPrompt(NamedTuple):
    prompt: str
    version_tag: str


class PromptService:
    OPTIMIZED_MATCH_PROMPT_NAME = "optimized_match"
    OPTIMIZED_MATCH_LANGUAGE = "en"
    OPTIMIZED_MATCH_ENVIRONMENT = "production"
    OPTIMIZED_MATCH_SCHEMA_ID = "cvai://prompts/optimized_match/response-schema/v4"
    OPTIMIZED_MATCH_PLACEHOLDERS = {"input_json", "domain_list_str", "dept_list_str"}
    OPTIMIZED_MATCH_SCHEMA_FIELDS = {
        "candidate_profile",
        "active_vacancy_summary",
        "ai_career_summary",
        "matched_vacancies",
    }
    OPTIMIZED_MATCH_VACANCY_SCHEMA_FIELDS = {
        "vacancy_id",
        "semantic_reason",
        "top_strength",
        "main_concern",
        "ai_match_explanation",
        "semantic_fit_score",
        "requirement_assessments",
    }
    OPTIMIZED_MATCH_ASSESSMENT_SCHEMA_FIELDS = {
        "requirement_id",
        "requirement",
        "category",
        "mandatory",
        "cv_evidence",
        "jd_evidence",
        "rationale",
        "match_type",
        "confidence",
        "impact",
    }
    OPTIMIZED_MATCH_REQUIRED_INSTRUCTION = "VACANCY COVERAGE:"
    OPTIMIZED_MATCH_NARRATIVE_INSTRUCTION = "DECISION NARRATIVES:"
    OPTIMIZED_MATCH_REQUIREMENT_INSTRUCTION = "REQUIREMENT ASSESSMENTS:"
    HIRING_RISK_PROMPT_NAME = "hiring_risk_explanation"
    HIRING_RISK_DEFAULT_VERSION = "default-1.0.0"
    HIRING_RISK_DEFAULT_TEMPLATE = """You explain deterministic hiring risks to recruiters.

INPUT:
{prompt_payload}

Return only the structured JSON required by the response schema.
You may write only title and explanation text for the supplied risk_code values.
Do not add risks or change risk codes, categories, severity, evidence, source, scores, match status, or manual-review decisions.
Use only the supplied evidence. Do not infer personal or protected attributes.
"""

    @classmethod
    def _get_default_prompt(cls, prompt_name: str) -> ResolvedPrompt | None:
        if prompt_name != cls.HIRING_RISK_PROMPT_NAME:
            return None
        return ResolvedPrompt(prompt=cls.HIRING_RISK_DEFAULT_TEMPLATE, version_tag=cls.HIRING_RISK_DEFAULT_VERSION)

    @classmethod
    def _get_default_prompt_identity(cls, prompt_name: str) -> str | None:
        default_prompt = cls._get_default_prompt(prompt_name)
        if default_prompt is None:
            return None
        prompt_hash = hashlib.sha256(default_prompt.prompt.encode("utf-8")).hexdigest()
        return f"{default_prompt.version_tag}:{prompt_hash}"

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
            from app.core.config import settings

            version_scope = settings.OPTIMIZED_PROMPT_VERSION
        else:
            version_scope = "active"
        cache_key = (
            f"prompt_tmpl:{prompt_name}:{version_scope}:{tenant_id or 'none'}:{model or 'none'}:"
            f"{target_schema or 'none'}:{language}:{environment}"
        )
        
        template = config_cache_manager.get(cache_key)
        
        if not template:
            try:
                template = cls._fetch_prompt_from_db(
                    prompt_name, tenant_id, model, target_schema, language, environment
                )
            except Exception as exc:
                logger.warning("Failed to resolve prompt '%s' from DB; checking built-in default: %s", prompt_name, type(exc).__name__)
                template = None
            if template:
                config_cache_manager.set(cache_key, template)

        if not template:
            default_prompt = cls._get_default_prompt(prompt_name)
            template = default_prompt.prompt if default_prompt is not None else None
            if template:
                logger.warning("Using built-in default prompt for '%s'.", prompt_name)
                
        if not template:
            logger.error(f"Prompt template '{prompt_name}' not found in DB.")
            raise PromptError("PROMPT_UNAVAILABLE")
                
        try:
            return template.format(**placeholders)
        except KeyError as e:
            logger.error(f"Missing required placeholder {e} in prompt template '{prompt_name}'")
            raise PromptError(f"Missing required placeholder {e}")

    @classmethod
    def get_prompt_with_version(
        cls,
        prompt_name: str,
        placeholders: dict[str, Any],
        tenant_id: Optional[str] = None,
        model: Optional[str] = None,
        target_schema: Optional[str] = None,
        language: str = "en",
        environment: str = "production",
    ) -> ResolvedPrompt:
        cache_key = f"prompt_tmpl_versioned:{prompt_name}:{tenant_id or 'none'}:{model or 'none'}:{target_schema or 'none'}:{language}:{environment}"
        cached = config_cache_manager.get(cache_key)
        if isinstance(cached, dict) and cached.get("template") and cached.get("version_tag"):
            template = str(cached["template"])
            version_tag = str(cached["version_tag"])
        else:
            try:
                record = cls._fetch_prompt_record_from_db(prompt_name, tenant_id, model, target_schema, language, environment)
            except Exception as exc:
                logger.warning("Failed to resolve prompt '%s' from DB; checking built-in default: %s", prompt_name, type(exc).__name__)
                record = None
            if record is None:
                default_prompt = cls._get_default_prompt(prompt_name)
                if default_prompt is None:
                    logger.error(f"Prompt template '{prompt_name}' not found in DB.")
                    raise PromptError("PROMPT_UNAVAILABLE")
                template = default_prompt.prompt
                version_tag = default_prompt.version_tag
                logger.warning("Using built-in default prompt for '%s'.", prompt_name)
            else:
                template = record.system_instruction
                version_tag = record.version_tag
            config_cache_manager.set(cache_key, {"template": template, "version_tag": version_tag})
        try:
            return ResolvedPrompt(prompt=template.format(**placeholders), version_tag=version_tag)
        except KeyError as e:
            logger.error(f"Missing required placeholder {e} in prompt template '{prompt_name}'")
            raise PromptError(f"Missing required placeholder {e}")

    @classmethod
    def get_active_prompt_version(
        cls,
        prompt_name: str,
        tenant_id: Optional[str] = None,
        model: Optional[str] = None,
        target_schema: Optional[str] = None,
        language: str = "en",
        environment: str = "production",
    ) -> str | None:
        cache_key = f"prompt_version:{prompt_name}:{tenant_id or 'none'}:{model or 'none'}:{target_schema or 'none'}:{language}:{environment}"
        cached = config_cache_manager.get(cache_key)
        if isinstance(cached, str) and cached:
            if cached != "__MISSING__":
                return cached
        try:
            record = cls._fetch_prompt_record_from_db(prompt_name, tenant_id, model, target_schema, language, environment)
        except Exception as exc:
            logger.warning(f"Failed to resolve active prompt version for '{prompt_name}': {exc}")
            record = None
        default_prompt = cls._get_default_prompt(prompt_name)
        version_tag = record.version_tag if record is not None else (default_prompt.version_tag if default_prompt is not None else None)
        config_cache_manager.set(cache_key, version_tag or "__MISSING__")
        return version_tag

    @classmethod
    def get_active_prompt_identity(
        cls,
        prompt_name: str,
        tenant_id: Optional[str] = None,
        model: Optional[str] = None,
        target_schema: Optional[str] = None,
        language: str = "en",
        environment: str = "production",
    ) -> str | None:
        cache_key = f"prompt_identity:{prompt_name}:{tenant_id or 'none'}:{model or 'none'}:{target_schema or 'none'}:{language}:{environment}"
        cached = config_cache_manager.get(cache_key)
        if isinstance(cached, str) and cached:
            if cached != "__MISSING__":
                return cached
        try:
            record = cls._fetch_prompt_record_from_db(prompt_name, tenant_id, model, target_schema, language, environment)
        except Exception as exc:
            logger.warning(f"Failed to resolve active prompt identity for '{prompt_name}': {exc}")
            record = None
        identity = None
        if record is not None:
            prompt_hash = hashlib.sha256(record.system_instruction.encode("utf-8")).hexdigest()
            identity = f"{record.version_tag}:{prompt_hash}"
        else:
            identity = cls._get_default_prompt_identity(prompt_name)
        config_cache_manager.set(cache_key, identity or "__MISSING__")
        return identity

    @classmethod
    def _fetch_prompt_record_from_db(
        cls,
        prompt_name: str,
        tenant_id: Optional[str],
        model: Optional[str],
        target_schema: Optional[str],
        language: str,
        environment: str,
    ) -> PromptTemplateMaster | None:
        with PostgresAppSession() as db:
            query = db.query(PromptTemplateMaster).filter(
                PromptTemplateMaster.prompt_name == prompt_name,
                PromptTemplateMaster.is_active == True,
                PromptTemplateMaster.language == language,
                PromptTemplateMaster.environment == environment,
            )
            if prompt_name == cls.OPTIMIZED_MATCH_PROMPT_NAME:
                from app.core.config import settings

                query = query.filter(PromptTemplateMaster.version_tag == settings.OPTIMIZED_PROMPT_VERSION)
            exact_match = query.filter(
                PromptTemplateMaster.tenant_id == tenant_id,
                PromptTemplateMaster.model == model,
                PromptTemplateMaster.target_schema == target_schema,
            ).order_by(PromptTemplateMaster.version_tag.desc()).first()
            if exact_match:
                db.expunge(exact_match)
                return exact_match
            if tenant_id is not None:
                tenant_fallback = query.filter(
                    PromptTemplateMaster.tenant_id.is_(None),
                    PromptTemplateMaster.model == model,
                    PromptTemplateMaster.target_schema == target_schema,
                ).order_by(PromptTemplateMaster.version_tag.desc()).first()
                if tenant_fallback:
                    db.expunge(tenant_fallback)
                    return tenant_fallback
            generic_match = query.filter(
                PromptTemplateMaster.tenant_id.is_(None),
                PromptTemplateMaster.model.is_(None),
                PromptTemplateMaster.target_schema.is_(None),
            ).order_by(PromptTemplateMaster.version_tag.desc()).first()
            if generic_match:
                db.expunge(generic_match)
            return generic_match

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
        record = cls._fetch_prompt_record_from_db(prompt_name, tenant_id, model, target_schema, language, environment)
        return record.system_instruction if record else None

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
            prompt_lines = prompt.system_instruction.lstrip().splitlines()
            if prompt_lines and prompt_lines[0].strip().lower() in {"/think", "/no_think"}:
                return PromptReadiness(False, "Required prompt contains a model-specific thinking directive.")
            if cls.OPTIMIZED_MATCH_REQUIRED_INSTRUCTION not in prompt.system_instruction:
                return PromptReadiness(False, "Required prompt does not enforce complete per-vacancy coverage.")
            if cls.OPTIMIZED_MATCH_NARRATIVE_INSTRUCTION not in prompt.system_instruction:
                return PromptReadiness(False, "Required prompt does not enforce detailed decision narratives.")
            if cls.OPTIMIZED_MATCH_REQUIREMENT_INSTRUCTION not in prompt.system_instruction:
                return PromptReadiness(False, "Required prompt does not enforce requirement-level assessments.")
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
            matched_vacancies_schema = schema.get("properties", {}).get("matched_vacancies", {}) if isinstance(schema, dict) else {}
            matched_vacancy_item_schema = matched_vacancies_schema.get("items", {}) if isinstance(matched_vacancies_schema, dict) else {}
            matched_vacancy_required = set(matched_vacancy_item_schema.get("required") or {}) if isinstance(matched_vacancy_item_schema, dict) else set()
            assessment_schema = matched_vacancy_item_schema.get("properties", {}).get("requirement_assessments", {}) if isinstance(matched_vacancy_item_schema, dict) else {}
            assessment_item_schema = assessment_schema.get("items", {}) if isinstance(assessment_schema, dict) else {}
            assessment_required = set(assessment_item_schema.get("required") or {}) if isinstance(assessment_item_schema, dict) else set()
            assessment_fields = set(assessment_item_schema.get("properties") or {}) if isinstance(assessment_item_schema, dict) else set()
            if (
                not isinstance(schema, dict)
                or schema.get("$id") != cls.OPTIMIZED_MATCH_SCHEMA_ID
                or schema.get("type") != "object"
                or not cls.OPTIMIZED_MATCH_SCHEMA_FIELDS.issubset(required_fields)
                or not cls.OPTIMIZED_MATCH_SCHEMA_FIELDS.issubset(schema_fields)
                or matched_vacancies_schema.get("type") != "array"
                or matched_vacancy_item_schema.get("type") != "object"
                or not cls.OPTIMIZED_MATCH_VACANCY_SCHEMA_FIELDS.issubset(matched_vacancy_required)
                or assessment_schema.get("type") != "array"
                or assessment_item_schema.get("type") != "object"
                or not cls.OPTIMIZED_MATCH_ASSESSMENT_SCHEMA_FIELDS.issubset(assessment_required)
                or not cls.OPTIMIZED_MATCH_ASSESSMENT_SCHEMA_FIELDS.issubset(assessment_fields)
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
        config_cache_manager.delete_by_pattern(f"prompt_tmpl_versioned:{prompt.prompt_name}:*")
        config_cache_manager.delete_by_pattern(f"prompt_version:{prompt.prompt_name}:*")
        config_cache_manager.delete_by_pattern(f"prompt_identity:{prompt.prompt_name}:*")
        
        return prompt
