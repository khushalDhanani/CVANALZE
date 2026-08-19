from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.rule_config_manager import RuleConfigManager
from app.schemas.analysis import OptimizedCandidateProfile
from app.schemas.normalized_resume import NormalizedResume
from app.schemas.profile import DynamicCandidateProfile
from app.services.candidate_domain_service import CandidateDomainService
from app.services.job_taxonomy import CandidateResumeDTO, TaxonomyClassifier


@dataclass
class CandidateAnalysisContext:
    """
    Encapsulates pre-computed candidate state for CV scoring.

    Computes normalized text, current role, experience, taxonomy classification,
    domain profile, domain matching text, and software candidate flag ONCE per CV,
    preventing redundant computations across multiple vacancy evaluations.
    """

    cv_text: str
    norm_text: str
    current_role: str | None = None
    candidate_experience: float | None = None
    candidate_ctc: float | None = None
    dynamic_profile: DynamicCandidateProfile | None = None
    optimized_profile: OptimizedCandidateProfile | None = None
    resume_json: dict[str, Any] | None = field(default=None)
    normalized_resume: NormalizedResume | None = None
    cand_domain_profile: dict[str, Any] = field(default_factory=dict)
    cand_domain: str = ""
    cand_tax_domain: str = ""
    cand_families: list[str] = field(default_factory=list)
    cand_primary_family: str | None = None
    taxonomy_confidence: float = 1.0
    taxonomy_match_status: str = "DB_MATCH"
    taxonomy_match_source: str | None = None
    professional_skills: list[str] = field(default_factory=list)
    experience_titles: list[str] = field(default_factory=list)
    education_evidence: list[str] = field(default_factory=list)
    domain_candidate_text: str = ""
    is_software_cand: bool = False
    cand_hierarchy: Any | None = None
    llm_core_skills: list[str] = field(default_factory=list)
    llm_inferred_skills: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        cv_text: str,
        *,
        candidate_experience: float | None = None,
        candidate_ctc: float | None = None,
        dynamic_profile: DynamicCandidateProfile | None = None,
        optimized_profile: OptimizedCandidateProfile | None = None,
        resume_json: dict[str, Any] | None = None,
        normalized_resume: NormalizedResume | None = None,
        deterministic_experience: float | None = None,
        domain_repository: Any = None,
    ) -> "CandidateAnalysisContext":
        # 1. Normalize CV & Profile Text
        profile_parts = [cv_text]
        current_role = None
        normalized_experience = normalized_resume.experience.authoritative_years if normalized_resume else None
        exp_years = normalized_experience if normalized_experience is not None else deterministic_experience
        if exp_years is None:
            exp_years = candidate_experience
        if exp_years is None and isinstance(resume_json, dict):
            raw_exp = resume_json.get("total_experience_years") or resume_json.get("experience_years")
            if raw_exp is not None:
                try:
                    exp_years = float(raw_exp)
                except (ValueError, TypeError):
                    pass

        if exp_years is None or (exp_years == 0.0 and normalized_resume and normalized_resume.experience.deterministic_years is None):
            if optimized_profile and optimized_profile.relevant_experience_years is not None:
                exp_years = float(optimized_profile.relevant_experience_years)

        if optimized_profile:
            optimized_profile = CandidateDomainService.validate_optimized_profile(
                optimized_profile, cv_text, resume_json, domain_repository
            )

        if optimized_profile:
            profile_parts.extend(
                [
                    *optimized_profile.professional_domains,
                    optimized_profile.current_role or "",
                    *optimized_profile.education_domains,
                    *optimized_profile.certifications,
                ]
            )
            current_role = optimized_profile.current_role


        elif dynamic_profile:
            profile_parts.extend(
                [
                    *dynamic_profile.professional_domains,
                    dynamic_profile.current_domain or "",
                    dynamic_profile.current_role or "",
                    *dynamic_profile.previous_roles,
                    *dynamic_profile.education_domains,
                ]
            )
            current_role = dynamic_profile.current_role


        if not current_role and normalized_resume and normalized_resume.employment:
            current_role = normalized_resume.employment[0].job_title.normalized_value

        if not current_role and resume_json:
            work_exp = resume_json.get("work_experience") or resume_json.get("experience") or []
            from app.services.resume_field_extractor import ResumeFieldExtractor
            latest = ResumeFieldExtractor.resolve_latest_employment(work_exp)
            current_role = latest.get("job_title") or resume_json.get("job_title") or (resume_json.get("contact_info") or {}).get("job_title")

        if current_role:
            validated_roles = CandidateDomainService.validate_job_roles(
                [current_role], cv_text, resume_json, domain_repository
            )
            current_role = validated_roles[0] if validated_roles else None

        if not current_role:
            m = re.search(
                r"(?:current\s*role|position|designation|job\s*title|post\s*held|profile)\s*:\s*([^\n]+)",
                cv_text,
                re.IGNORECASE,
            )
            if m:
                validated_roles = CandidateDomainService.validate_job_roles(
                    [m.group(1)], cv_text, resume_json, domain_repository
                )
                current_role = validated_roles[0] if validated_roles else None

        if not current_role and cv_text:
            from app.services.resume_field_extractor import ResumeFieldExtractor
            sections = ResumeFieldExtractor._split_sections(cv_text.splitlines())
            header_role = ResumeFieldExtractor.extract_title_from_summary_or_header(
                sections.get("summary", []), cv_text.splitlines()
            )
            if header_role:
                validated_roles = CandidateDomainService.validate_job_roles(
                    [header_role], cv_text, resume_json, domain_repository
                )
                current_role = validated_roles[0] if validated_roles else None

        # Text normalization inline (mirrors ScoringEngine._normalize_text)
        raw_combined = " ".join(filter(None, profile_parts))
        norm_text = re.sub(r"[^a-zA-Z0-9\s#+./-]", " ", raw_combined).lower()
        norm_text = re.sub(r"\s+", " ", norm_text).strip()

        # 2. Taxonomy Classification (cached)
        resume_evidence = CandidateResumeDTO.from_resume(cv_text, resume_json=resume_json)
        cand_tax_domain, cand_families_list, taxonomy_confidence, taxonomy_status, taxonomy_source = (
            TaxonomyClassifier.classify_candidate_with_confidence(cv_text, resume_json=resume_json)
        )
        cand_families = list(cand_families_list)

        # Taxonomy overrides using LLM domain are no longer permitted.
        # Gemma may provide grounded evidence (skills/roles) which inform the deterministic
        # classification during profile extraction, but cannot directly set the candidate domain.
        if optimized_profile and optimized_profile.professional_domains:
            llm_domain = optimized_profile.professional_domains[0]
            canonical_domains = set(RuleConfigManager.get_taxonomy_rules().canonical_domains)
            if llm_domain not in canonical_domains:
                import logging as _log
                _log.getLogger("cv_analyzer").warning(
                    f"[CANDIDATE_CONTEXT] LLM domain '{llm_domain}' not in DB canonicals."
                )

        cand_primary_family = cand_families[0] if cand_families else None

        # 3. Candidate Domain Profile Extraction
        cand_domain_profile = CandidateDomainService.extract_candidate_domain_profile(
            cv_text=cv_text,
            dynamic_profile=dynamic_profile,
            optimized_profile=optimized_profile,
            resume_json=resume_json,
            domain_repository=domain_repository,
        )
        profile_domain = str(cand_domain_profile.get("professional_domain") or "").strip()
        profile_department = str(cand_domain_profile.get("recommended_department") or "").strip()
        profile_taxonomy_confidence = float(cand_domain_profile.get("taxonomy_confidence") or 0.0)
        use_profile_taxonomy = bool(profile_domain or profile_department) and profile_taxonomy_confidence >= taxonomy_confidence
        if use_profile_taxonomy:
            if profile_domain:
                cand_tax_domain = profile_domain
            if profile_department:
                cand_families = [profile_department]
                cand_primary_family = profile_department
            taxonomy_confidence = profile_taxonomy_confidence
            current_taxonomy_status = taxonomy_status.value if hasattr(taxonomy_status, "value") else str(taxonomy_status)
            taxonomy_status = str(cand_domain_profile.get("taxonomy_match_status") or current_taxonomy_status)
            taxonomy_source = str(cand_domain_profile.get("taxonomy_match_source") or taxonomy_source or "") or None

        cand_domain = cand_domain_profile.get("professional_domain", "")

        # 4. Domain Candidate Text Construction
        domain_candidate_text = CandidateDomainService.build_domain_candidate_text(
            cv_text=cv_text,
            current_role=current_role,
            dynamic_profile=dynamic_profile,
            optimized_profile=optimized_profile,
            domain_repository=domain_repository,
        )

        # 5. Software Candidate Guard Flag from configured evidence patterns.
        guard_patterns = RuleConfigManager.get_compiled_cross_domain_guard()["software_candidate_patterns"]
        software_evidence = " ".join([domain_candidate_text, cand_tax_domain, cand_domain, current_role or ""])
        is_software_cand = any(pattern.search(software_evidence) for pattern in guard_patterns)

        return cls(
            cv_text=cv_text,
            norm_text=norm_text,
            current_role=current_role,
            candidate_experience=exp_years,
            candidate_ctc=candidate_ctc,
            dynamic_profile=dynamic_profile,
            optimized_profile=optimized_profile,
            resume_json=resume_json,
            normalized_resume=normalized_resume,
            cand_domain_profile=cand_domain_profile,
            cand_domain=cand_domain,
            cand_tax_domain=cand_tax_domain,
            cand_families=cand_families,
            cand_primary_family=cand_primary_family,
            taxonomy_confidence=taxonomy_confidence,
            taxonomy_match_status=taxonomy_status.value if hasattr(taxonomy_status, "value") else str(taxonomy_status),
            taxonomy_match_source=taxonomy_source,
            professional_skills=resume_evidence.skills,
            experience_titles=resume_evidence.experience_titles,
            education_evidence=resume_evidence.education,
            domain_candidate_text=domain_candidate_text,
            is_software_cand=is_software_cand,
            cand_hierarchy=None,
            llm_core_skills=optimized_profile.core_skills if optimized_profile else (dynamic_profile.core_skills if dynamic_profile else []),
            llm_inferred_skills=optimized_profile.inferred_skills if optimized_profile else [],
        )

    def apply_optimized_profile(
        self,
        optimized_profile: OptimizedCandidateProfile | None,
        *,
        domain_repository: Any = None,
    ) -> None:
        """Apply LLM enrichment once while keeping deterministic resume values authoritative."""
        if optimized_profile is None:
            return

        optimized_profile = CandidateDomainService.validate_optimized_profile(
            optimized_profile, self.cv_text, self.resume_json, domain_repository
        )

        deterministic_role = self.current_role
        deterministic_domain = self.cand_tax_domain
        deterministic_profile_domain = self.cand_domain
        deterministic_families = list(self.cand_families)
        deterministic_primary_family = self.cand_primary_family
        self.optimized_profile = optimized_profile
        self.professional_skills = list(dict.fromkeys([*self.professional_skills, *optimized_profile.core_skills]))
        if optimized_profile.current_role:
            self.experience_titles = list(dict.fromkeys([optimized_profile.current_role, *self.experience_titles]))
        self.education_evidence = list(dict.fromkeys([*self.education_evidence, *optimized_profile.education_domains]))
        if optimized_profile.current_role and not self.current_role:
            self.current_role = optimized_profile.current_role
        if self.candidate_experience is None and optimized_profile.relevant_experience_years is not None:
            try:
                self.candidate_experience = float(optimized_profile.relevant_experience_years)
            except (TypeError, ValueError):
                pass

        profile_parts = [
            self.cv_text,
            *optimized_profile.core_skills,
            *optimized_profile.professional_domains,
            optimized_profile.current_role or "",
            *optimized_profile.education_domains,
            *optimized_profile.certifications,
        ]
        self.norm_text = re.sub(r"[^a-zA-Z0-9\s#+./-]", " ", " ".join(filter(None, profile_parts))).lower()
        self.norm_text = re.sub(r"\s+", " ", self.norm_text).strip()
        self.llm_core_skills = list(optimized_profile.core_skills)
        self.llm_inferred_skills = list(optimized_profile.inferred_skills)

        # Taxonomy overrides using LLM domain are no longer permitted.
        if optimized_profile.professional_domains and self.cand_tax_domain in ("", "Unknown"):
            llm_domain = optimized_profile.professional_domains[0]
            canonical_domains = set(RuleConfigManager.get_taxonomy_rules().canonical_domains)
            if llm_domain not in canonical_domains:
                import logging as _log
                _log.getLogger("cv_analyzer").warning(
                    f"[CANDIDATE_CONTEXT] apply_optimized_profile: LLM domain '{llm_domain}' not in DB canonicals."
                )

        self.cand_domain_profile = CandidateDomainService.extract_candidate_domain_profile(
            cv_text=self.cv_text,
            optimized_profile=optimized_profile,
            resume_json=self.resume_json,
            domain_repository=domain_repository,
        )
        self.cand_domain = deterministic_profile_domain or self.cand_domain_profile.get("professional_domain", self.cand_domain)
        profile_department = str(self.cand_domain_profile.get("recommended_department") or "").strip()
        if self.cand_domain and deterministic_domain in ("", "Unknown"):
            self.cand_tax_domain = self.cand_domain
        if profile_department and not deterministic_families:
            self.cand_families = [profile_department]
            self.cand_primary_family = profile_department
        if deterministic_domain not in ("", "Unknown"):
            self.cand_tax_domain = deterministic_domain
            self.cand_families = deterministic_families
            self.cand_primary_family = deterministic_primary_family
        if deterministic_role:
            self.current_role = deterministic_role
        self.domain_candidate_text = CandidateDomainService.build_domain_candidate_text(
            cv_text=self.cv_text,
            current_role=self.current_role,
            optimized_profile=optimized_profile,
            domain_repository=domain_repository,
        )
        guard_patterns = RuleConfigManager.get_compiled_cross_domain_guard()["software_candidate_patterns"]
        software_evidence = " ".join([self.domain_candidate_text, self.cand_tax_domain, self.cand_domain, self.current_role or ""])
        self.is_software_cand = any(pattern.search(software_evidence) for pattern in guard_patterns)
