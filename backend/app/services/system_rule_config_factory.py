from __future__ import annotations

from datetime import datetime, timezone

from app.core.rule_config_manager import (
    CandidateTaxonomyRule,
    CrossDomainGuard,
    DomainEmbeddingRules,
    DownstreamGates,
    FallbackDefaults,
    FieldRuleConfig,
    GlobalTierBoundary,
    LexicalWeights,
    MatchScoringRules,
    PrefilterRules,
    ResumeQualityRules,
    ScoringParameters,
    ScoringRules,
    TermMatching,
    TaxonomyCondition,
    TaxonomyRuleBranch,
    TaxonomyRules,
    TierThresholds,
    UnifiedRuleConfig,
    VacancyTaxonomyRule,
    HiringRiskConfig,
    HiringRiskPolicy,
    WorkflowRules,
)


class SystemRuleConfigFactory:
    """Build the conservative, reviewable baseline used for first-time setup."""

    VERSION = "system-default-v2"

    @classmethod
    def build(cls) -> UnifiedRuleConfig:
        config = UnifiedRuleConfig(
            version=cls.VERSION,
            description="System-generated conservative baseline. Review all rules before activation.",
            last_updated=datetime.now(timezone.utc).isoformat(),
            global_confidence_tiers={
                "HIGH": GlobalTierBoundary(min_score=0.80, max_score=1.00),
                "MEDIUM": GlobalTierBoundary(min_score=0.50, max_score=0.79),
                "LOW": GlobalTierBoundary(min_score=0.00, max_score=0.49),
            },
            fields=cls._fields(),
            scoring=cls._scoring(),
            workflow=WorkflowRules(),
            hiring_risks=HiringRiskConfig(
                policies={
                    "MIN_EXPERIENCE_FAILED": HiringRiskPolicy(severity="CRITICAL", manual_review=False),
                    "EXPERIENCE_UNKNOWN": HiringRiskPolicy(severity="UNKNOWN", manual_review=True),
                    "MISSING_MANDATORY_SKILL": HiringRiskPolicy(severity="CRITICAL", manual_review=False),
                    "MISSING_PREFERRED_SKILL": HiringRiskPolicy(severity="MEDIUM", manual_review=False),
                    "UNVERIFIED_SKILL": HiringRiskPolicy(severity="MEDIUM", manual_review=True),
                    "DOMAIN_MISMATCH": HiringRiskPolicy(severity="HIGH", manual_review=False),
                    "OVERQUALIFIED": HiringRiskPolicy(severity="LOW", manual_review=False),
                }
            ),
        )
        return config

    @staticmethod
    def _fields() -> dict[str, FieldRuleConfig]:
        common_tiers = TierThresholds(high_min=0.80, medium_min=0.50, low_min=0.00)
        return {
            "name": FieldRuleConfig(
                field_name="name",
                description="Conservative candidate-name confidence rules.",
                confidence_scoring={"verified_header": 0.90, "email_username_fallback": 0.30},
                tier_thresholds=common_tiers.model_copy(deep=True),
                downstream_gates=DownstreamGates(min_acceptance_confidence=0.50, reject_email_fallback_as_unverified=True),
                keywords={"header_denylist": ["resume", "curriculum vitae", "profile", "summary"]},
            ),
            "location": FieldRuleConfig(
                field_name="location",
                description="Conservative location confidence rules requiring explicit contact evidence.",
                confidence_scoring={"explicit_contact_location": 0.90, "unverified_location": 0.30},
                tier_thresholds=common_tiers.model_copy(deep=True),
                downstream_gates=DownstreamGates(min_acceptance_confidence=0.50, require_gazetteer_for_high=False),
                keywords={"gazetteer": [], "blacklist": ["dear", "sir", "madam", "salutation"]},
            ),
            "job_title": FieldRuleConfig(
                field_name="job_title",
                description="Conservative job-title validation rules.",
                confidence_scoring={"explicit_title": 0.90, "inferred_title": 0.50},
                tier_thresholds=common_tiers.model_copy(deep=True),
                downstream_gates=DownstreamGates(min_acceptance_confidence=0.50, max_word_count=10, max_char_length=100),
                keywords={
                    "narrative_starters": ["graduated", "worked"], 
                    "narrative_phrases": [], 
                    "keywords": [
                        "ENGINEER", "DEVELOPER", "MANAGER", "EXECUTIVE", "ANALYST", "OFFICER", "CONSULTANT", "DIRECTOR", 
                        "LEAD", "SPECIALIST", "INSPECTOR", "ADMINISTRATOR", "TECHNICIAN", "INCHARGE", "IN CHARGE", 
                        "OPERATOR", "ASSISTANT", "CHEMIST", "SCIENTIST", "PROGRAMMER", "ARCHITECT", "DESIGNER", 
                        "COORDINATOR", "SUPERVISOR", "HEAD", "SR.", "JR."
                    ]
                },
            ),
            "company_name": FieldRuleConfig(
                field_name="company_name",
                description="Conservative employer-name validation rules.",
                confidence_scoring={"explicit_company": 0.90, "inferred_company": 0.50},
                tier_thresholds=common_tiers.model_copy(deep=True),
                downstream_gates=DownstreamGates(min_acceptance_confidence=0.50, max_char_length=120),
                keywords={
                    "generic_section_headers": ["experience", "education", "skills", "projects"],
                    "suffixes": [
                        "ltd", "limited", "pvt", "private", "inc", "incorporated", "llc", "llp", "corp", 
                        "corporation", "industries", "solutions", "enterprises", "infosys", "infotech", 
                        "technologies", "technology", "pharma", "chemicals", "remedies", "generics", "organics", "techno lab", "techno labs"
                    ]
                },
            ),
        }

    @staticmethod
    def _scoring() -> ScoringRules:
        general_branch = TaxonomyRuleBranch(
            conditions=[TaxonomyCondition(scope="full_text", keywords=["general"], mode="any")]
        )
        candidate_branch = TaxonomyRuleBranch(
            conditions=[TaxonomyCondition(scope="candidate_full_text", keywords=["general"], mode="any")]
        )
        return ScoringRules(
            match=MatchScoringRules(
                term_matching=TermMatching(
                    stop_phrases=["e.g", "eg", "e.g.", "etc", "etc.", "i.e", "i.e."],
                    noise_words=[
                        "programming", "language", "framework", "the", "systems", "principles",
                        "write", "integrating", "with", "services", "backend", "of", "work",
                        "working", "job", "service", "task", "role", "duty", "item", "helper",
                    ],
                    aliases={
                        "widgets": ["widget", "widgets", "ui"],
                        "navigation": ["navigation", "route", "routing", "maps", "gps", "directions"],
                        "restful apis": ["api", "apis", "rest", "restful", "http"],
                        "json": ["json", "payload"],
                        "integrating with backend services": ["backend", "api", "apis", "firebase", "http"],
                        "version control systems": ["git", "github", "gitlab", "versioning", "vcs"],
                        "problem-solving": ["problem-solving", "problem solving"],
                    },
                ),
                fallback_defaults=FallbackDefaults(
                    recommended_department="General Operations",
                    professional_domain="General Operations",
                    suitable_roles=[],
                ),
                cross_domain_guard=CrossDomainGuard(
                    software_candidate_keywords=["software"],
                    non_it_job_keywords=["operations"],
                    software_requirement_keywords=["software"],
                    domain_guard_terms={},
                    domain_mismatch_multiplier=0.25,
                    domain_mismatch_score_cap=25.0,
                    mandatory_failure_score_impact=50.0,
                ),
                scoring_parameters=ScoringParameters(
                    career_transition_role_score=50.0,
                    role_divergence_score=70.0,
                    default_role_score=50.0,
                    below_min_exp_multiplier=50.0,
                    overqualification_penalty=20.0,
                    domain_default_match_score=50.0,
                    low_coverage_threshold=0.50,
                    false_positive_score_cap=80.0,
                    match_high_threshold=80.0,
                    match_medium_threshold=50.0,
                    mandatory_failure_penalty=20.0,
                    max_score_on_failure=50.0,
                    llm_semantic_weight=0.10,
                    max_llm_boost=10.0,
                    component_weights={
                        "role": 0.20,
                        "skills": 0.25,
                        "experience": 0.20,
                        "education": 0.10,
                        "domain": 0.15,
                        "technology": 0.05,
                        "certification": 0.025,
                        "responsibilities": 0.025,
                    },
                ),
            ),
            prefilter=PrefilterRules(
                stop_words=["and", "the", "with", "for"],
                lexical_weights=LexicalWeights(
                    department_match=30.0,
                    title_term_match=20.0,
                    required_skill_match=20.0,
                    preferred_keyword_match=10.0,
                    experience_suitability=20.0,
                ),
                rrf_k_constant=60.0,
            ),
            taxonomy=TaxonomyRules(
                canonical_domains=["General Operations"],
                canonical_families=["General Professional"],
                default_domain="General Operations",
                default_family="General Professional",
                vacancy_rules=[
                    VacancyTaxonomyRule(
                        name="general_operations",
                        domain="General Operations",
                        family="General Professional",
                        branches=[general_branch],
                    )
                ],
                candidate_rules=[
                    CandidateTaxonomyRule(
                        name="general_professional",
                        domain="General Operations",
                        families=["General Professional"],
                        branches=[candidate_branch],
                    )
                ],
            ),
            resume_quality=ResumeQualityRules(
                section_patterns={
                    "contact": r"\b(contact|email|phone|address|linkedin|location)\b",
                    "experience": r"\b(experience|employment|work history)\b",
                    "education": r"\b(education|academic|qualification|degree)\b",
                    "skills": r"\b(skills|technologies|competencies)\b",
                },
                core_sections=["contact", "experience", "education", "skills"],
                section_weight=0.10,
                contact_weights={"email": 1.0, "phone": 1.0, "linkedin": 0.5, "location": 0.5},
                location_acceptance_min_confidence=0.50,
                density_scores=[],
                default_density_score=0.05,
                heading_normalization=[],
            ),
            domain_embedding=DomainEmbeddingRules(
                categories=["skills", "job_titles", "departments", "technologies"],
                canonical_equivalents={},
            ),
        )
