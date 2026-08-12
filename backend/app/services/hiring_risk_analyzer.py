import logging
from typing import Any
import json

from app.schemas.match import JobMatchResult, HiringRisk, RiskSeverity
from app.core.rule_config_manager import RuleConfigManager
from app.services.ollama_transport import OllamaTransport
from app.schemas.candidate_context import CandidateAnalysisContext
from app.schemas.job_context import JobEvaluationContext

logger = logging.getLogger("cv_analyzer")

class HiringRiskAnalyzer:
    @classmethod
    def generate_risks(
        cls,
        match_result: JobMatchResult,
        context: CandidateAnalysisContext,
        job_ctx: JobEvaluationContext,
    ) -> None:
        """
        Analyzes the deterministic JobMatchResult, generates deterministic risk evidence,
        and prompts Gemma for recruiter-facing explanations.
        """
        try:
            config = RuleConfigManager.get_config()
            risk_policy = config.hiring_risks
            risks: list[HiringRisk] = []
            
            # Group generic failures into RiskEvidenceEvent-like structures
            events = []
            
            # 1. Mandatory Failures
            for failure in match_result.mandatory_fails:
                failure_code = failure.get("failure_code")
                if failure_code:
                    events.append({
                        "risk_code": failure_code,
                        "category": "Requirements",
                        "evidence": f"{failure['requirement']} - {failure['details']}",
                        "source": "RequirementEvaluator"
                    })

            # 2. Missing Mandatory Skills (Create custom failure_code MISSING_MANDATORY_SKILL if needed, though they are in mandatory_fails)
            # Match evaluators now emit MISSING_MANDATORY_SKILL directly in mandatory_failures, but just in case:
            if match_result.missing_skills and not any(e["risk_code"] == "MISSING_MANDATORY_SKILL" for e in events):
                events.append({
                    "risk_code": "MISSING_MANDATORY_SKILL",
                    "category": "Skills",
                    "evidence": f"Missing mandatory skills: {', '.join(match_result.missing_skills)}",
                    "source": "RequirementEvaluator"
                })
                
            # 3. Domain Mismatch
            if match_result.domain_mismatch_capped and not any(e["risk_code"] == "DOMAIN_MISMATCH" for e in events):
                events.append({
                    "risk_code": "DOMAIN_MISMATCH",
                    "category": "Domain",
                    "evidence": match_result.domain_mismatch_reason or "Domain match capped",
                    "source": "CrossDomainGuard"
                })

            for event in events:
                risk_code = event["risk_code"]
                policy = risk_policy.policies.get(risk_code)
                if not policy:
                    logger.debug(f"[HIRING_RISKS] Ignored unknown or disabled risk code: {risk_code}")
                    continue
                
                risk = HiringRisk(
                    risk_code=risk_code,
                    category=event["category"],
                    severity=policy.severity,
                    title=f"Detected {risk_code}",
                    explanation=event["evidence"],
                    evidence=[event["evidence"]],
                    source=event["source"],
                    requires_manual_review=policy.manual_review
                )
                risks.append(risk)

            if not risks:
                return

            # Ask Gemma for explanations
            cls._generate_explanations(risks, match_result, context)
            
            match_result.hiring_risks = risks

        except Exception as e:
            logger.error(f"[HIRING_RISKS] Failed to generate risks: {e}", exc_info=True)
            # Fail gracefully, don't modify scores or status

    @classmethod
    def _generate_explanations(cls, risks: list[HiringRisk], match_result: JobMatchResult, context: CandidateAnalysisContext) -> None:
        """Prompts Gemma to generate readable explanations for the deterministic risks."""
        # We only pass the risk structures.
        prompt_payload = {
            "job_title": match_result.job_title,
            "risks": [
                {
                    "risk_code": r.risk_code,
                    "category": r.category,
                    "evidence": r.evidence
                }
                for r in risks
            ]
        }
        
        try:
            from pydantic import BaseModel
            class Explanation(BaseModel):
                risk_code: str
                title: str
                explanation: str
            class ExplanationsOutput(BaseModel):
                explanations: list[Explanation]
                
            from app.services.llm_service import OllamaLLMService
            from app.services.prompt_service import PromptService
            
            try:
                prompt = PromptService.get_prompt("hiring_risk_explanation", placeholders={"prompt_payload": json.dumps(prompt_payload, indent=2)})
                prompt_version = "1.0" # Ideally from PromptService config if available, hardcoded to 1.0 for caching
            except Exception as e:
                logger.warning(f"[HIRING_RISKS] Prompt unavailable, using deterministic fallbacks: {e}")
                return
            
            # Simple hash for cache key based on job and risks
            cache_raw = f"{match_result.job_id}_{json.dumps(prompt_payload, sort_keys=True)}"
            import hashlib
            cache_key = hashlib.md5(cache_raw.encode()).hexdigest()

            response = OllamaLLMService.generate_structured_json(
                operation="hiring_risks_explanation",
                prompt=prompt,
                prompt_version=prompt_version,
                cache_key=cache_key,
                response_model=ExplanationsOutput,
                think=False,
                options={"temperature": 0.0}
            )
            
            if response and response.validated:
                data = response.validated
                explanations = {item.risk_code: item for item in data.explanations}
                
                for risk in risks:
                    if risk.risk_code in explanations:
                        # Only update title and explanation, discard any hallucinated severity or code
                        risk.title = explanations[risk.risk_code].title
                        risk.explanation = explanations[risk.risk_code].explanation
        except Exception as e:
            logger.warning(f"[HIRING_RISKS] Gemma explanation generation failed, using deterministic fallbacks: {e}")
