from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Any

from app.core.rule_config_manager import RuleConfigManager
from app.schemas.analysis import OptimizedCandidateProfile
from app.schemas.normalized_resume import NormalizedResume
from app.schemas.profile import DynamicCandidateProfile
from app.services.candidate_domain_service import CandidateDomainService
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
from app.services.job_taxonomy import TaxonomyClassifier


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
    domain_candidate_text: str = ""
    is_software_cand: bool = False
    cand_hierarchy: Any | None = None

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
        normalized_experience = normalized_resume.experience.deterministic_years if normalized_resume else None
        exp_years = deterministic_experience if deterministic_experience is not None else normalized_experience
        if exp_years is None:
            exp_years = candidate_experience
        if exp_years is None and isinstance(resume_json, dict):
            raw_exp = resume_json.get("total_experience_years") or resume_json.get("experience_years")
            if raw_exp is not None:
                try:
                    exp_years = float(raw_exp)
                except (ValueError, TypeError):
                    pass

        if optimized_profile:
            profile_parts.extend(
                [
                    *optimized_profile.core_skills,
                    *optimized_profile.inferred_skills,
                    *optimized_profile.professional_domains,
                    optimized_profile.current_role or "",
                    *optimized_profile.education_domains,
                    *optimized_profile.certifications,
                ]
            )
            current_role = optimized_profile.current_role

            if exp_years is None and optimized_profile.relevant_experience_years is not None:
                try:
                    exp_years = float(optimized_profile.relevant_experience_years)
                except (ValueError, TypeError):
                    pass

        elif dynamic_profile:
            profile_parts.extend(
                [
                    *dynamic_profile.core_skills,
                    *dynamic_profile.professional_domains,
                    dynamic_profile.current_domain or "",
                    dynamic_profile.current_role or "",
                    *dynamic_profile.previous_roles,
                    *dynamic_profile.education_domains,
                ]
            )
            current_role = dynamic_profile.current_role

            if exp_years is None and dynamic_profile.relevant_experience_years is not None:
                try:
                    exp_years = float(dynamic_profile.relevant_experience_years)
                except (ValueError, TypeError):
                    pass

        if not current_role and normalized_resume and normalized_resume.employment:
            current_role = normalized_resume.employment[0].job_title.normalized_value

        cand_name_clean = ""
        if isinstance(resume_json, dict):
            raw_cand_name = resume_json.get("name") or resume_json.get("candidate_name") or ""
            if isinstance(raw_cand_name, str):
                cand_name_clean = raw_cand_name.strip().lower()

        denied_roles = {
            "personal details", "personal details:", "objective", "summary", "profile",
            "education", "skills", "technical skills", "experience", "work experience",
            "key achievements", "achievements", "certifications", "contact information",
            "projects", "declarations", "declaration", "hobbies", "languages"
        }

        def is_valid_role(r: str) -> bool:
            if not r or len(r.strip()) < 2:
                return False
            clean = r.strip().lower()
            if clean in denied_roles or clean.endswith(":") or clean in cand_name_clean:
                return False
            if cand_name_clean and len(cand_name_clean) > 3 and cand_name_clean in clean:
                return False
            return True

        if current_role and not is_valid_role(current_role):
            current_role = None

        if not current_role:
            m = re.search(
                r"(?:current\s*role|position|designation|job\s*title)\s*:\s*([^\n]+)",
                cv_text,
                re.IGNORECASE,
            )
            if m and is_valid_role(m.group(1)):
                current_role = m.group(1).strip()

        # Text normalization inline (mirrors ScoringEngine._normalize_text)
        raw_combined = " ".join(filter(None, profile_parts))
        norm_text = re.sub(r"[^a-zA-Z0-9\s#+./-]", " ", raw_combined).lower()
        norm_text = re.sub(r"\s+", " ", norm_text).strip()

        # 2. Taxonomy Classification (cached)
        cand_tax_domain, cand_families_list = TaxonomyClassifier.classify_candidate(cv_text, resume_json=resume_json)
        cand_families = list(cand_families_list)

        # Override with LLM classification only if domain is validated against DB canonicals
        if optimized_profile and optimized_profile.professional_domains:
            llm_domain = optimized_profile.professional_domains[0]
            canonical_domains = set(RuleConfigManager.get_taxonomy_rules().canonical_domains)
            if llm_domain in canonical_domains:
                cand_tax_domain = llm_domain
                # Map canonical domain back to compatible families using taxonomy rules
                llm_families = []
                taxonomy = RuleConfigManager.get_taxonomy_rules()
                for r in taxonomy.candidate_rules:
                    if r.domain == cand_tax_domain:
                        llm_families.extend(r.families)
                seen = set()
                mapped_families = [f for f in llm_families if not (f in seen or seen.add(f))]
                if mapped_families:
                    cand_families = mapped_families
                else:
                    cand_families = [cand_tax_domain]
            else:
                import logging as _log
                _log.getLogger("cv_analyzer").warning(
                    f"[CANDIDATE_CONTEXT] LLM domain '{llm_domain}' not in DB canonicals — keeping deterministic classification '{cand_tax_domain}'."
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
        if optimized_profile and optimized_profile.professional_domains:
            cand_domain_profile["professional_domain"] = optimized_profile.professional_domains[0]

        cand_domain = cand_domain_profile.get("professional_domain", "")

        # 4. Domain Candidate Text Construction
        domain_candidate_text = CandidateDomainService.build_domain_candidate_text(
            cv_text=cv_text,
            current_role=current_role,
            dynamic_profile=dynamic_profile,
            optimized_profile=optimized_profile,
            domain_repository=domain_repository,
        )

        # 5. Software Candidate Guard Flag — use DB family compatibility instead of hardcoded patterns
        it_software_family = "Software Engineering & Development"
        is_software_cand = False
        if cand_primary_family:
            is_compat, status, score = DynamicTaxonomyService.check_family_compatibility(cand_primary_family, it_software_family)
            if is_compat and score is not None and score >= 0.4:
                is_software_cand = True
        if not is_software_cand:
            is_software_cand = "Information Technology" in cand_tax_domain or "Software" in cand_tax_domain

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
            domain_candidate_text=domain_candidate_text,
            is_software_cand=is_software_cand,
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

        self.optimized_profile = optimized_profile
        if optimized_profile.current_role:
            self.current_role = optimized_profile.current_role
        if self.candidate_experience is None and optimized_profile.relevant_experience_years is not None:
            try:
                self.candidate_experience = float(optimized_profile.relevant_experience_years)
            except (TypeError, ValueError):
                pass

        profile_parts = [
            self.cv_text,
            *optimized_profile.core_skills,
            *optimized_profile.inferred_skills,
            *optimized_profile.professional_domains,
            optimized_profile.current_role or "",
            *optimized_profile.education_domains,
            *optimized_profile.certifications,
        ]
        self.norm_text = re.sub(r"[^a-zA-Z0-9\s#+./-]", " ", " ".join(filter(None, profile_parts))).lower()
        self.norm_text = re.sub(r"\s+", " ", self.norm_text).strip()

        if optimized_profile.professional_domains:
            llm_domain = optimized_profile.professional_domains[0]
            canonical_domains = set(RuleConfigManager.get_taxonomy_rules().canonical_domains)
            if llm_domain in canonical_domains:
                self.cand_tax_domain = llm_domain
                mapped_families: list[str] = []
                for rule in RuleConfigManager.get_taxonomy_rules().candidate_rules:
                    if rule.domain == self.cand_tax_domain:
                        mapped_families.extend(rule.families)
                self.cand_families = list(dict.fromkeys(mapped_families)) or [self.cand_tax_domain]
                self.cand_primary_family = self.cand_families[0]
            else:
                import logging as _log
                _log.getLogger("cv_analyzer").warning(
                    f"[CANDIDATE_CONTEXT] apply_optimized_profile: LLM domain '{llm_domain}' not in DB canonicals — keeping deterministic '{self.cand_tax_domain}'."
                )

        self.cand_domain_profile = CandidateDomainService.extract_candidate_domain_profile(
            cv_text=self.cv_text,
            optimized_profile=optimized_profile,
            resume_json=self.resume_json,
            domain_repository=domain_repository,
        )
        if optimized_profile.professional_domains:
            self.cand_domain_profile["professional_domain"] = optimized_profile.professional_domains[0]
        self.cand_domain = self.cand_domain_profile.get("professional_domain", self.cand_domain)
        self.domain_candidate_text = CandidateDomainService.build_domain_candidate_text(
            cv_text=self.cv_text,
            current_role=self.current_role,
            optimized_profile=optimized_profile,
            domain_repository=domain_repository,
        )
        guard = RuleConfigManager.get_compiled_cross_domain_guard()
        # Replace hardcoded patterns with DB family compatibility check
        it_software_family = "Software Engineering & Development"
        self.is_software_cand = False
        if self.cand_primary_family:
            is_compat, status, score = DynamicTaxonomyService.check_family_compatibility(self.cand_primary_family, it_software_family)
            if is_compat and score is not None and score >= 0.4:
                self.is_software_cand = True
        if not self.is_software_cand:
            self.is_software_cand = "Information Technology" in self.cand_domain or "Software" in self.cand_domain
        _ = guard  # retained for backward compat; patterns no longer used for is_software_cand
