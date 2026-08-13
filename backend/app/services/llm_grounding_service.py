from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.prompts.match_analysis import build_job_requirements
from app.schemas.analysis import (
    ClassifiedRequirementItem,
    OptimizedLLMMatchResponse,
    OptimizedVacancyMatch,
    RequirementAssessment,
    RequirementEvidence,
)
from app.services.candidate_domain_service import CandidateDomainService
from app.services.quality_metrics import QualityMetrics

_NORMALIZE = re.compile(r"[^a-z0-9+#./-]+")


@dataclass(frozen=True)
class GroundingReport:
    assertions: int = 0
    grounded_assertions: int = 0
    invalid_vacancy_ids: list[str] = field(default_factory=list)
    missing_vacancy_ids: list[str] = field(default_factory=list)
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
        expected_vacancy_ids = {
            str(vacancy.get("vacancy_id") or vacancy.get("id"))
            for vacancy in vacancies
            if vacancy.get("vacancy_id") is not None or vacancy.get("id") is not None
        }
        response_vacancy_ids = {str(match.vacancy_id) for match in response.matched_vacancies}
        missing_ids = sorted(expected_vacancy_ids - response_vacancy_ids)
        if not settings.LLM_GROUNDING_ENABLED:
            profile = CandidateDomainService.validate_optimized_profile(response.candidate_profile, cv_text)
            matches = []
            for match in response.matched_vacancies:
                requirements, evidence = cls._compatibility_lineage(match.requirement_assessments)
                matches.append(
                    match.model_copy(
                        update={
                            "matched_skills": CandidateDomainService.validate_skills(match.matched_skills, cv_text),
                            "inferred_skills": CandidateDomainService.validate_skills(match.inferred_skills, cv_text, source_confidence=0.35),
                            "classified_requirements": requirements or match.classified_requirements,
                            "evidence_snippets": evidence or match.evidence_snippets,
                        }
                    )
                )
            return response.model_copy(update={"candidate_profile": profile, "matched_vacancies": matches}), GroundingReport(missing_vacancy_ids=missing_ids)

        vacancy_sources = {
            str(vacancy.get("vacancy_id") or vacancy.get("id")): json.dumps(vacancy, sort_keys=True, default=str)
            for vacancy in vacancies
            if vacancy.get("vacancy_id") is not None or vacancy.get("id") is not None
        }
        vacancy_records = {
            str(vacancy.get("vacancy_id") or vacancy.get("id")): vacancy
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

            assessments, assessment_grounded, assessment_total, assessment_unsupported = cls._ground_requirement_assessments(
                match.requirement_assessments,
                vacancy=vacancy_records[vacancy_id],
                cv_text=cv_text,
            )
            assertions += assessment_total
            grounded += assessment_grounded
            unsupported.extend(f"assessment:{vacancy_id}:{claim}" for claim in assessment_unsupported)

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

            if assessments:
                requirements, evidence = cls._compatibility_lineage(assessments)

            validated_matches.append(
                match.model_copy(
                    update={
                        "matched_skills": matched_skills,
                        "inferred_skills": inferred_skills,
                        "evidence_snippets": evidence,
                        "classified_requirements": requirements,
                        "requirement_assessments": assessments,
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
            missing_vacancy_ids=missing_ids,
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
            missing_vacancy_ids=len(missing_ids),
            unsupported_claims=len(unsupported),
        )
        return validated, report

    @classmethod
    def _ground_requirement_assessments(
        cls,
        assessments: list[RequirementAssessment],
        *,
        vacancy: dict[str, Any],
        cv_text: str,
    ) -> tuple[list[RequirementAssessment], int, int, list[str]]:
        expected = build_job_requirements(vacancy)
        expected_by_id = {item["requirement_id"]: item for item in expected}
        supplied_by_id = {item.requirement_id: item for item in assessments}
        unsupported = [f"unknown:{item.requirement_id}" for item in assessments if item.requirement_id not in expected_by_id]
        grounded = 0
        validated: list[RequirementAssessment] = []

        for requirement_id, source_item in expected_by_id.items():
            assessment = supplied_by_id.get(requirement_id)
            if assessment is None:
                unsupported.append(f"omitted:{requirement_id}")
                validated.append(cls._not_assessable(source_item, "The model did not return an assessment for this supplied requirement."))
                continue

            jd_supported = _supported(assessment.jd_evidence, source_item["jd_evidence"])
            positive_match = assessment.match_type in {"DIRECT", "INFERRED", "PARTIAL"}
            cv_supported = bool(assessment.cv_evidence.strip()) and _supported(assessment.cv_evidence, cv_text)
            if not jd_supported:
                unsupported.append(f"jd:{requirement_id}")
            if positive_match and not cv_supported:
                unsupported.append(f"cv:{requirement_id}")
                assessment = cls._not_assessable(source_item, "The model's positive match did not include CV-grounded evidence.")
            else:
                assessment = assessment.model_copy(
                    update={
                        "requirement": source_item["requirement"],
                        "category": source_item["category"],
                        "mandatory": source_item["mandatory"],
                        "cv_evidence": assessment.cv_evidence if positive_match else "",
                        "jd_evidence": source_item["jd_evidence"],
                        "impact": "CRITICAL" if source_item["mandatory"] and assessment.match_type == "MISSING" else assessment.impact,
                    }
                )
                grounded += int(jd_supported and (not positive_match or cv_supported))
            validated.append(assessment)

        return validated, grounded, len(expected), unsupported

    @staticmethod
    def _not_assessable(source_item: dict[str, Any], rationale: str) -> RequirementAssessment:
        return RequirementAssessment(
            requirement_id=source_item["requirement_id"],
            requirement=source_item["requirement"],
            category=source_item["category"],
            mandatory=source_item["mandatory"],
            cv_evidence="",
            jd_evidence=source_item["jd_evidence"],
            rationale=rationale,
            match_type="NOT_ASSESSABLE",
            confidence=0.0,
            impact="CRITICAL" if source_item["mandatory"] else "HIGH",
        )

    @staticmethod
    def _compatibility_lineage(
        assessments: list[RequirementAssessment],
    ) -> tuple[list[ClassifiedRequirementItem], dict[str, RequirementEvidence]]:
        status_by_match_type = {
            "DIRECT": "SATISFIED",
            "INFERRED": "PARTIALLY_SATISFIED",
            "PARTIAL": "PARTIALLY_SATISFIED",
            "MISSING": "FAILED",
            "NOT_ASSESSABLE": "UNVERIFIED",
        }
        requirements = [
            ClassifiedRequirementItem(
                requirement_id=item.requirement_id,
                description=item.requirement,
                tier="MANDATORY" if item.mandatory else "PREFERRED",
                status=status_by_match_type[item.match_type],
                failure_reason=None if item.match_type == "DIRECT" else item.rationale,
            )
            for item in assessments
        ]
        evidence = {
            item.requirement_id: RequirementEvidence(cv_evidence=item.cv_evidence, vacancy_evidence=item.jd_evidence)
            for item in assessments
            if item.cv_evidence
        }
        return requirements, evidence

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
