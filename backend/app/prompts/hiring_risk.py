from __future__ import annotations

HIRING_RISK_PROMPT_NAME = "hiring_risk_explanation"
HIRING_RISK_PROMPT_VERSION = "default-1.0.0"
HIRING_RISK_PROMPT_TEMPLATE = """You explain deterministic hiring risks to recruiters.

INPUT:
{prompt_payload}

Return only the structured JSON required by the response schema.
You may write only title and explanation text for the supplied risk_code values.
Do not add risks or change risk codes, categories, severity, evidence, source, scores, match status, or manual-review decisions.
Use only the supplied evidence. Do not infer personal or protected attributes.
"""
