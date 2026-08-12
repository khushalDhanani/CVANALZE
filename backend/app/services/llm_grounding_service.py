from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.schemas.analysis import OptimizedLLMMatchResponse, OptimizedVacancyMatch
from app.services.candidate_domain_service import CandidateDomainService
from app.services.quality_metrics import QualityMetrics

_NORMALIZE = re.compile(r"[^a-z0-9+#./-]+")


@dataclass(frozen=True)
class GroundingReport:
    assertions: int = 0
    grounded_assertions: int = 0
    invalid_vacancy_ids: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return self.grounded_assertions / self.assertions if self.assertions else 1.0


def _normalized(value: object) -> str:
    return " ".join(_NORMALIZE.sub(" ", str(value or "").lower()).split())


def _supported(claim: str, source: str) -> bool:
    normalized_claim = _normalized(claim)
    normalized_source = _normalized(source)
    if not normalized_claim:
        return False
    if normalized_claim in normalized_source:
        return True
    meaningful_tokens = {token for token in normalized_claim.split() if len(token) >= 3}
    return bool(meaningful_tokens) and meaningful_tokens.issubset(set(normalized_source.split()))


class LLMGroundingService:
    """Remove unsupported LLM claims before they can enrich deterministic scoring."""

    @classmethod
    def validate_optimized_response(
        cls,
        response: OptimizedLLMMatchResponse,
        *,
        cv_text: str,
        vacancies: list[dict[str, Any]],
    ) -> tuple[OptimizedLLMMatchResponse, GroundingReport]:
        if not settings.LLM_GROUNDING_ENABLED:
            profile = CandidateDomainService.validate_optimized_profile(response.candidate_profile, cv_text)
            matches = [
                match.model_copy(
                    update={
                        "matched_skills": CandidateDomainService.validate_skills(match.matched_skills, cv_text),
                        "inferred_skills": CandidateDomainService.validate_skills(
                            match.inferred_skills, cv_text, source_confidence=0.35
                        ),
                    }
                )
                for match in response.matched_vacancies
            ]
            return response.model_copy(update={"candidate_profile": profile, "matched_vacancies": matches}), GroundingReport()

        vacancy_sources = {
            str(vacancy.get("vacancy_id") or vacancy.get("id")): json.dumps(vacancy, sort_keys=True, default=str)
            for vacancy in vacancies
            if vacancy.get("vacancy_id") is not None or vacancy.get("id") is not None
        }
        assertions = 0
        grounded = 0
        invalid_ids: list[str] = []
        unsupported: list[str] = []
        validated_matches: list[OptimizedVacancyMatch] = []

        for match in response.matched_vacancies:
            vacancy_id = str(match.vacancy_id)
            vacancy_source = vacancy_sources.get(vacancy_id)
            assertions += 1
            if vacancy_source is None:
                invalid_ids.append(vacancy_id)
                continue
            grounded += 1

            matched_skills, matched_grounded, matched_total = cls._filter_skills(match.matched_skills, cv_text)
            inferred_skills, inferred_grounded, inferred_total = cls._filter_skills(match.inferred_skills, cv_text)
            assertions += matched_total + inferred_total
            grounded += matched_grounded + inferred_grounded
            unsupported.extend(skill for skill in match.matched_skills + match.inferred_skills if skill not in matched_skills + inferred_skills)

            evidence = {}
            for evidence_id, item in match.evidence_snippets.items():
                assertions += 1
                if _supported(item.cv_evidence, cv_text) and _supported(item.vacancy_evidence, vacancy_source):
                    evidence[evidence_id] = item
                    grounded += 1
                else:
                    unsupported.append(f"evidence:{vacancy_id}:{evidence_id}")

            valid_evidence_ids = set(evidence)
            requirements = []
            for requirement in match.classified_requirements:
                if requirement.status.upper() == "SATISFIED" and requirement.requirement_id not in valid_evidence_ids:
                    requirement = requirement.model_copy(
                        update={"status": "UNVERIFIED", "failure_reason": "The model claim did not include source-grounded dual evidence."}
                    )
                requirements.append(requirement)

            validated_matches.append(
                match.model_copy(
                    update={
                        "matched_skills": matched_skills,
                        "inferred_skills": inferred_skills,
                        "evidence_snippets": evidence,
                        "classified_requirements": requirements,
                    }
                )
            )

        profile = response.candidate_profile
        core_skills, core_grounded, core_total = cls._filter_skills(profile.core_skills, cv_text)
        inferred_profile, profile_grounded, profile_total = cls._filter_skills(profile.inferred_skills, cv_text)
        education, education_grounded, education_total = cls._filter_claims(profile.education_domains, cv_text)
        certifications, certifications_grounded, certifications_total = cls._filter_claims(profile.certifications, cv_text)
        professional_domains, domains_grounded, domains_total = cls._filter_claims(profile.professional_domains, cv_text)
        strengths, strengths_grounded, strengths_total = cls._filter_claims(profile.strengths, cv_text)
        suitable_roles, roles_grounded, roles_total = cls._filter_roles(profile.suitable_job_roles, cv_text)
        assertions += core_total + profile_total + education_total + certifications_total + domains_total + strengths_total + roles_total
        grounded += core_grounded + profile_grounded + education_grounded + certifications_grounded + domains_grounded + strengths_grounded + roles_grounded
        unsupported.extend(skill for skill in profile.core_skills + profile.inferred_skills if skill not in core_skills + inferred_profile)
        validated_current_roles = cls._filter_roles([profile.current_role], cv_text)[0] if profile.current_role else []
        current_role = validated_current_roles[0] if validated_current_roles else None
        if profile.current_role:
            assertions += 1
            grounded += int(current_role is not None)
            if current_role is None:
                unsupported.append(f"role:{profile.current_role}")

        experience = profile.relevant_experience_years
        if experience is not None:
            assertions += 1
            experience_pattern = re.compile(rf"\b{re.escape(f'{experience:g}')}\s*(?:\+\s*)?(?:years?|yrs?)\b", re.IGNORECASE)
            if experience_pattern.search(cv_text):
                grounded += 1
            else:
                unsupported.append(f"experience:{experience}")
                experience = None

        report = GroundingReport(
            assertions=assertions,
            grounded_assertions=grounded,
            invalid_vacancy_ids=invalid_ids,
            unsupported_claims=unsupported[:100],
        )
        validated_profile = profile.model_copy(
            update={
                "core_skills": core_skills,
                "inferred_skills": inferred_profile,
                "relevant_experience_years": experience,
                "education_domains": education,
                "certifications": certifications,
                "current_role": current_role,
                "professional_domains": professional_domains,
                "recommended_department": profile.recommended_department if profile.recommended_department and _supported(profile.recommended_department, cv_text) else None,
                "professional_domain": profile.professional_domain if profile.professional_domain and _supported(profile.professional_domain, cv_text) else None,
                "strengths": strengths,
                "suitable_job_roles": suitable_roles,
            }
        )
        validated_profile = CandidateDomainService.validate_optimized_profile(validated_profile, cv_text)
        summary = response.ai_career_summary if report.ratio >= 0.8 else ""
        validated = response.model_copy(
            update={"candidate_profile": validated_profile, "matched_vacancies": validated_matches, "ai_career_summary": summary}
        )
        QualityMetrics.record(
            "grounding",
            assertions=assertions,
            grounded_assertions=grounded,
            invalid_vacancy_ids=len(invalid_ids),
            unsupported_claims=len(unsupported),
        )
        return validated, report

    @staticmethod
    def _filter_claims(claims: list[str], source: str) -> tuple[list[str], int, int]:
        supported = [claim for claim in claims if _supported(claim, source)]
        return supported, len(supported), len(claims)

    @staticmethod
    def _filter_skills(claims: list[str], source: str) -> tuple[list[str], int, int]:
        supported = [claim for claim in claims if _supported(claim, source)]
        validated = CandidateDomainService.validate_skills(supported, source)
        return validated, len(validated), len(claims)

    @staticmethod
    def _filter_roles(claims: list[str], source: str) -> tuple[list[str], int, int]:
        supported = [claim for claim in claims if _supported(claim, source)]
        validated = CandidateDomainService.validate_job_roles(supported, source)
        return validated, len(validated), len(claims)
