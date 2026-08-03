import re
from dataclasses import dataclass, field
from typing import Any

from app.core.rule_config_manager import RuleConfigManager
from app.schemas.analysis import OptimizedCandidateProfile
from app.schemas.normalized_resume import NormalizedResume
from app.schemas.profile import DynamicCandidateProfile
from app.services.candidate_domain_service import CandidateDomainService
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

        if optimized_profile:
            profile_parts.extend([
                *optimized_profile.core_skills,
                *optimized_profile.inferred_skills,
                *optimized_profile.professional_domains,
                optimized_profile.current_role or "",
                *optimized_profile.education_domains,
                *optimized_profile.certifications,
            ])
            current_role = optimized_profile.current_role
            
            if exp_years is None and optimized_profile.relevant_experience_years is not None:
                try:
                    exp_years = float(optimized_profile.relevant_experience_years)
                except (ValueError, TypeError):
                    pass
            
        elif dynamic_profile:
            profile_parts.extend([
                *dynamic_profile.core_skills,
                *dynamic_profile.professional_domains,
                dynamic_profile.current_domain or "",
                dynamic_profile.current_role or "",
                *dynamic_profile.previous_roles,
                *dynamic_profile.education_domains,
            ])
            current_role = dynamic_profile.current_role
            
            if exp_years is None and dynamic_profile.relevant_experience_years is not None:
                try:
                    exp_years = float(dynamic_profile.relevant_experience_years)
                except (ValueError, TypeError):
                    pass

        if not current_role and normalized_resume and normalized_resume.employment:
            current_role = normalized_resume.employment[0].job_title.normalized_value

        if not current_role:
            m = re.search(r"(?:current\s*role|position|title)\s*:\s*([^\n]+)", cv_text, re.IGNORECASE)
            if m:
                current_role = m.group(1).strip()
            else:
                m_header = re.search(r"##\s*([^\n]+)", cv_text)
                if m_header:
                    current_role = m_header.group(1).strip()

        # Text normalization inline (mirrors ScoringEngine._normalize_text)
        raw_combined = " ".join(filter(None, profile_parts))
        norm_text = re.sub(r"[^a-zA-Z0-9\s#+./-]", " ", raw_combined).lower()
        norm_text = re.sub(r"\s+", " ", norm_text).strip()

        # 2. Taxonomy Classification (cached)
        cand_tax_domain, cand_families_list = TaxonomyClassifier.classify_candidate(cv_text, resume_json=resume_json)
        cand_families = list(cand_families_list)
        
        # Override with LLM classification if available
        if optimized_profile and optimized_profile.professional_domains:
            cand_tax_domain = optimized_profile.professional_domains[0]
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

        # 5. Software Candidate Guard Flag
        compiled_guard = RuleConfigManager.get_compiled_cross_domain_guard()
        sw_patterns = compiled_guard["software_candidate_patterns"]
        is_software_cand = (
            "Information Technology" in cand_domain
            or "Software" in cand_domain
            or any(p.search(norm_text) for p in sw_patterns)
        )

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
            self.cand_tax_domain = optimized_profile.professional_domains[0]
            mapped_families: list[str] = []
            for rule in RuleConfigManager.get_taxonomy_rules().candidate_rules:
                if rule.domain == self.cand_tax_domain:
                    mapped_families.extend(rule.families)
            self.cand_families = list(dict.fromkeys(mapped_families)) or [self.cand_tax_domain]
            self.cand_primary_family = self.cand_families[0]

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
        self.is_software_cand = (
            "Information Technology" in self.cand_domain
            or "Software" in self.cand_domain
            or any(pattern.search(self.norm_text) for pattern in guard["software_candidate_patterns"])
        )
