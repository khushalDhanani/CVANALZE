from __future__ import annotations

import hashlib
import json
import logging
import re

from pydantic import BaseModel, ConfigDict

from app.core.config import settings
from app.core.rule_config_manager import RuleConfigManager
from app.repositories.llm_cache import LLMCacheRepository
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext
from app.schemas.match import HiringRisk, JobMatchResult, RiskEvidenceEvent
from app.services.llm_service import OllamaLLMService
from app.services.prompt_service import PromptService

logger = logging.getLogger("cv_analyzer")


class HiringRiskExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    risk_code: str
    title: str
    explanation: str


class HiringRiskExplanationsOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanations: list[HiringRiskExplanation]


class HiringRiskAnalyzer:
    PROMPT_NAME = "hiring_risk_explanation"
    DEFERRED_INTEGRITY_DOMAIN = "education"

    @classmethod
    def generate_risks(
        cls,
        match_result: JobMatchResult,
        context: CandidateAnalysisContext | None,
        job_ctx: JobEvaluationContext | None,
    ) -> None:
        """Build deterministic risks first, then optionally enrich only their display text."""
        try:
            config = RuleConfigManager.get_config()
            events = cls._collect_evidence_events(match_result)
            risks: list[HiringRisk] = []

            for event in events:
                if event.integrity_domain == cls.DEFERRED_INTEGRITY_DOMAIN:
                    logger.info(f"[HIRING_RISKS] Deferred education risk code: {event.failure_code}")
                    continue
                policy = config.hiring_risks.policies.get(event.failure_code)
                if policy is None:
                    logger.debug(f"[HIRING_RISKS] Ignored unknown risk code: {event.failure_code}")
                    continue
                if not policy.enabled:
                    logger.info(f"[HIRING_RISKS] Ignored disabled risk code: {event.failure_code}")
                    continue
                fallback_title = policy.title or f"Detected {event.failure_code}"
                fallback_explanation = " ".join(event.evidence)
                risks.append(
                    HiringRisk(
                        risk_code=event.failure_code,
                        category=policy.category,
                        severity=policy.severity,
                        title=fallback_title,
                        explanation=fallback_explanation,
                        evidence=event.evidence,
                        source=policy.source or event.source,
                        requires_manual_review=policy.manual_review,
                    )
                )

            match_result.hiring_risks = risks
            if risks:
                cls._generate_explanations(risks, match_result, cls.get_policy_version(config), context)
        except Exception as exc:
            logger.error(f"[HIRING_RISKS] Failed to generate risks: {exc}", exc_info=True)

    @classmethod
    def _collect_evidence_events(cls, match_result: JobMatchResult) -> list[RiskEvidenceEvent]:
        events: dict[str, RiskEvidenceEvent] = {}

        def add_event(event: RiskEvidenceEvent) -> None:
            existing = events.get(event.failure_code)
            if existing is None:
                events[event.failure_code] = event
                return
            existing.evidence.extend(item for item in event.evidence if item not in existing.evidence)

        for failure in match_result.mandatory_failures:
            integrity_domain = cls._integrity_domain(failure.failure_code, failure.requirement_id)
            add_event(
                RiskEvidenceEvent(
                    failure_code=failure.failure_code,
                    requirement_id=failure.requirement_id,
                    evidence=[failure.description, failure.reason],
                    source="RequirementEvaluator",
                    integrity_domain=integrity_domain,
                )
            )

        if not match_result.mandatory_failures:
            for failure in match_result.mandatory_fails:
                failure_code = str(failure.get("failure_code") or "").strip()
                if not failure_code:
                    continue
                requirement_id = str(failure.get("requirement_id") or "").strip() or None
                evidence = [str(value).strip() for value in (failure.get("requirement"), failure.get("details")) if str(value or "").strip()]
                add_event(
                    RiskEvidenceEvent(
                        failure_code=failure_code,
                        requirement_id=requirement_id,
                        evidence=evidence,
                        source="RequirementEvaluator",
                        integrity_domain=cls._integrity_domain(failure_code, requirement_id),
                    )
                )

        if match_result.missing_skills and "MISSING_MANDATORY_SKILL" not in events:
            add_event(
                RiskEvidenceEvent(
                    failure_code="MISSING_MANDATORY_SKILL",
                    requirement_id="req_mandatory_skills",
                    evidence=[f"Missing mandatory skills: {', '.join(match_result.missing_skills)}"],
                    source="RequirementEvaluator",
                )
            )

        if match_result.domain_mismatch_capped and "DOMAIN_MISMATCH" not in events:
            add_event(
                RiskEvidenceEvent(
                    failure_code="DOMAIN_MISMATCH",
                    requirement_id="req_domain_mismatch",
                    evidence=[match_result.domain_mismatch_reason or "Domain match capped"],
                    source="CrossDomainGuard",
                )
            )

        return list(events.values())

    @classmethod
    def _integrity_domain(cls, failure_code: str, requirement_id: str | None) -> str | None:
        normalized_requirement = (requirement_id or "").upper()
        if failure_code.upper().startswith("EDUCATION_") or normalized_requirement.startswith("REQ_EDUCATION"):
            return cls.DEFERRED_INTEGRITY_DOMAIN
        return None

    @staticmethod
    def get_policy_version(config=None) -> str:
        active_config = config or RuleConfigManager.get_config()
        policy_json = json.dumps(active_config.hiring_risks.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        policy_hash = hashlib.sha256(policy_json.encode("utf-8")).hexdigest()
        return f"{active_config.version}:{policy_hash}"

    @classmethod
    def _generate_explanations(
        cls,
        risks: list[HiringRisk],
        match_result: JobMatchResult,
        policy_version: str,
        context: CandidateAnalysisContext | None = None,
    ) -> None:
        prompt_payload = {
            "job_title": match_result.job_title,
            "risks": [
                {
                    "risk_code": risk.risk_code,
                    "category": risk.category,
                    "evidence": [cls._sanitize_prompt_text(item, context) for item in risk.evidence],
                }
                for risk in risks
            ],
        }

        try:
            resolved_prompt = PromptService.get_prompt_with_version(
                cls.PROMPT_NAME,
                placeholders={"prompt_payload": json.dumps(prompt_payload, indent=2)},
            )
        except Exception as exc:
            logger.warning(f"[HIRING_RISKS] Prompt unavailable, using deterministic fallbacks: {exc}")
            return

        payload_json = json.dumps(prompt_payload, sort_keys=True, separators=(",", ":"))
        source_hash = hashlib.sha256(f"{resolved_prompt.prompt}\0{payload_json}".encode("utf-8")).hexdigest()
        cache_key = LLMCacheRepository.extraction_cache_key(
            document_hash=source_hash,
            candidate_id=match_result.job_id,
            prompt_version=resolved_prompt.version_tag,
            model_version=settings.OLLAMA_MODEL,
            extraction_version=f"hiring-risk-policy:{policy_version}",
        )

        try:
            response = OllamaLLMService.generate_structured_json(
                operation="hiring_risks_explanation",
                prompt=resolved_prompt.prompt,
                prompt_version=resolved_prompt.version_tag,
                cache_key=cache_key,
                response_model=HiringRiskExplanationsOutput,
                think=False,
                options={"temperature": 0.0},
            )
            if response is None:
                return
            explanations = {item.risk_code: item for item in response.explanations}
            for risk in risks:
                explanation = explanations.get(risk.risk_code)
                if explanation is not None:
                    risk.title = explanation.title
                    risk.explanation = explanation.explanation
        except Exception as exc:
            logger.warning(f"[HIRING_RISKS] Gemma explanation generation failed, using deterministic fallbacks: {exc}")

    @staticmethod
    def _sanitize_prompt_text(value: str, context: CandidateAnalysisContext | None) -> str:
        sanitized = value
        contact_info = context.resume_json.get("contact_info", {}) if context and isinstance(context.resume_json, dict) else {}
        if isinstance(contact_info, dict):
            for key in ("name", "full_name", "email", "phone", "dob", "date_of_birth", "age", "gender", "nationality", "address", "location"):
                protected_value = str(contact_info.get(key) or "").strip()
                if protected_value:
                    sanitized = re.sub(re.escape(protected_value), "[REDACTED]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[REDACTED]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", "[REDACTED]", sanitized)
        sanitized = re.sub(
            r"\b(?:candidate\s+name|full\s+name|email|phone|dob|date\s+of\s+birth|age|gender|sex|nationality|address)\s*[:=-]\s*[^,;\n]+",
            "[REDACTED]",
            sanitized,
            flags=re.IGNORECASE,
        )
        return sanitized
