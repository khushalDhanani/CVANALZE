from __future__ import annotations
import re
from typing import Any

from app.core.rule_config_manager import PolicyRegistry, RuleConfigManager
from app.repositories.department_domain import (
    DepartmentDomainRepository,
    department_domain_repository,
)
from app.schemas.analysis import OptimizedCandidateProfile, OptimizedVacancyMatch
from app.schemas.classification_types import MatchStatus
from app.schemas.domain import DepartmentDomain
from app.schemas.profile import DynamicCandidateProfile
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
from app.services.job_taxonomy import TaxonomyClassifier


class CandidateDomainService:
    """
    Dedicated service for candidate domain detection, candidate text profile extraction,
    and department term resolution.
    """

    _ENTITY_CONFIDENCE_THRESHOLD = 0.70  # policy-approved-constant

    @classmethod
    def extract_candidate_domain_profile(
        cls,
        cv_text: str,
        dynamic_profile: DynamicCandidateProfile | None = None,
        optimized_profile: OptimizedCandidateProfile | None = None,
        resume_json: dict[str, Any] | None = None,
        domain_repository: DepartmentDomainRepository | None = None,
    ) -> dict[str, Any]:
        """
        Identifies candidate's most suitable department and professional domain
        from skills, experience, education, and projects.
        """
        if resume_json is None and cv_text:
            from app.services.resume_field_extractor import ResumeFieldExtractor

            resume_json = ResumeFieldExtractor.extract(cv_text)
        combined_parts = [cv_text]
        skill_candidates: list[tuple[str, float]] = []
        education_list: list[str] = []
        projects_list: list[str] = []
        responsibilities_list: list[str] = []
        role_candidates: list[tuple[str, float]] = []

        if optimized_profile:
            skill_candidates.extend((skill, 0.45) for skill in optimized_profile.core_skills)
            skill_candidates.extend((skill, 0.35) for skill in optimized_profile.inferred_skills)
            education_list.extend(optimized_profile.education_domains)
            if optimized_profile.current_role:
                role_candidates.append((optimized_profile.current_role, 0.55))
            combined_parts.extend(optimized_profile.professional_domains)

        if dynamic_profile:
            dynamic_confidence = {"HIGH": 0.50, "MEDIUM": 0.40}.get(dynamic_profile.confidence.upper(), 0.25)
            skill_candidates.extend((skill, dynamic_confidence) for skill in dynamic_profile.core_skills)
            education_list.extend(dynamic_profile.education_domains)
            if dynamic_profile.current_role:
                role_candidates.append((dynamic_profile.current_role, dynamic_confidence + 0.10))
            role_candidates.extend((role, dynamic_confidence) for role in dynamic_profile.previous_roles)

        if resume_json:
            if isinstance(resume_json.get("skills"), list):
                skill_candidates.extend((skill, 0.45) for skill in resume_json["skills"] if isinstance(skill, str))
            elif isinstance(resume_json.get("skills"), dict):
                raw_skills = resume_json["skills"]
                if isinstance(raw_skills.get("all_skills"), list):
                    skill_candidates.extend((skill, 0.45) for skill in raw_skills["all_skills"] if isinstance(skill, str) and skill.strip())
                for sub in raw_skills.values():
                    if isinstance(sub, list):
                        skill_candidates.extend((skill, 0.45) for skill in sub if isinstance(skill, str) and skill.strip())
            if isinstance(resume_json.get("education"), list):
                for edu in resume_json["education"]:
                    if isinstance(edu, dict):
                        education_list.append(f"{edu.get('degree', '')} {edu.get('field_of_study', '')}")
                    else:
                        education_list.append(str(edu))
            if isinstance(resume_json.get("projects"), list):
                for proj in resume_json["projects"]:
                    if isinstance(proj, dict):
                        projects_list.append(f"{proj.get('title', '')}: {proj.get('description', '')}")
                    else:
                        projects_list.append(str(proj))
            experience_items = resume_json.get("work_experience") or resume_json.get("experience") or []
            if isinstance(experience_items, list):
                for experience in experience_items:
                    if not isinstance(experience, dict):
                        continue
                    role = experience.get("job_title") or experience.get("title") or experience.get("position")
                    if role:
                        role_candidates.append((str(role), 0.60))
                    for responsibility in experience.get("responsibilities") or []:
                        if isinstance(responsibility, str) and responsibility.strip():
                            responsibilities_list.append(responsibility.strip())

        if not skill_candidates:
            skill_candidates.extend((skill, 0.40) for skill in cls._extract_cv_skill_lines(cv_text))
        if not role_candidates:
            role_candidates.extend((role, 0.50) for role in cls._extract_cv_role_headers(cv_text))

        repo = domain_repository or department_domain_repository
        skills_set = set(cls._validate_skills(skill_candidates, cv_text, resume_json, repo))
        roles_list = cls.validate_job_roles([role for role, _ in role_candidates], cv_text, resume_json, repo, role_candidates)

        # Enforce that education does not override established professional experience
        active_education = []
        if not roles_list and not projects_list:
            active_education = education_list

        combined_text = " ".join(
            filter(
                None,
                combined_parts + sorted(skills_set) + active_education + projects_list + responsibilities_list + roles_list,
            )
        ).lower()

        # 1. Dynamic Vector & MSSQL taxonomy resolution
        role_evidence = [*roles_list, *responsibilities_list, *projects_list]
        role_input = " ".join(role_evidence) if role_evidence else combined_text
        dyn_res = DynamicTaxonomyService.resolve_candidate_role_and_domain(
            role_or_summary=role_input,
            skills=sorted(skills_set),
        )

        if dyn_res.match_status in (MatchStatus.DB_MATCH, MatchStatus.PARTIAL_MATCH):
            industry_dept = dyn_res.industry_department or dyn_res.industry_domain or dyn_res.db_department_name
            prof_domain = dyn_res.industry_domain or dyn_res.db_department_name or ""
            recommended_dept = industry_dept or prof_domain
            resolved_role = dyn_res.industry_designation or dyn_res.db_designation_name
            suitable_roles = [resolved_role] if resolved_role else []
            taxonomy_confidence = dyn_res.confidence
            taxonomy_match_status = dyn_res.match_status.value
            taxonomy_match_source = dyn_res.match_source
        else:
            tax_rules = RuleConfigManager.get_taxonomy_rules()
            w_exp = tax_rules.evidence_weight_experience
            w_resp = tax_rules.evidence_weight_responsibilities
            w_skills = tax_rules.evidence_weight_skills
            
            exp_text = " ".join(roles_list).lower()
            resp_text = " ".join([*projects_list, *responsibilities_list]).lower()
            skills_text = " ".join(skills_set).lower()
            
            dept_scores: list[tuple[float, DepartmentDomain]] = []
            for matcher in repo.get_domain_matchers():
                score = 0.0
                evidence_sources = 0
                total_matches = 0
                if exp_text:
                    matches = matcher.keyword_match_count(exp_text)
                    score += matches * w_exp
                    evidence_sources += int(matches > 0)
                    total_matches += matches
                if resp_text:
                    matches = matcher.keyword_match_count(resp_text)
                    score += matches * w_resp
                    evidence_sources += int(matches > 0)
                    total_matches += matches
                if skills_text:
                    matches = matcher.keyword_match_count(skills_text)
                    score += matches * w_skills
                    evidence_sources += int(matches > 0)
                    total_matches += matches
                    
                if score > 0 and (evidence_sources >= 2 or total_matches >= 2):
                    dept_scores.append((score, matcher.domain))

            if dept_scores:
                best_score, best_domain = max(dept_scores, key=lambda item: (item[0], -item[1].priority))
                recommended_dept = best_domain.department_name
                prof_domain = best_domain.domain_name
                suitable_roles = best_domain.default_roles
                evidence_weight_total = w_exp + w_resp + w_skills
                taxonomy_confidence = min(1.0, best_score / evidence_weight_total) if evidence_weight_total > 0 else 0.0
                taxonomy_match_status = MatchStatus.DB_MATCH.value
                taxonomy_match_source = "DepartmentDomainMaster"
            else:
                recommended_dept = None
                prof_domain = None
                suitable_roles = []
                taxonomy_confidence = 0.0
                taxonomy_match_status = "NO_CONFIDENT_MATCH"
                taxonomy_match_source = dyn_res.match_source

        # Build custom roles from structured profile roles first
        custom_roles: list[str] = []
        if roles_list:
            custom_roles.extend(roles_list)

        # When no structured roles available, dynamically infer from actual resume content
        if not custom_roles:
            inferred = cls._infer_roles_from_resume(cv_text, resume_json, repo)
            if inferred:
                custom_roles = inferred
            else:
                custom_roles = cls.validate_job_roles(suitable_roles, cv_text, resume_json, repo, taxonomy_inferred=True)

        from app.services.evidence_ranker import EvidenceRanker

        # Build evidence-based strengths using EvidenceRanker
        strengths = EvidenceRanker.extract_evidence_based_strengths(skills_set, education_list, projects_list)

        return {
            "recommended_department": recommended_dept,
            "professional_domain": prof_domain,
            "strengths": strengths,
            "suitable_job_roles": custom_roles[:4],
            "taxonomy_confidence": taxonomy_confidence,
            "taxonomy_match_status": taxonomy_match_status,
            "taxonomy_match_source": taxonomy_match_source,
        }

    @classmethod
    def _infer_roles_from_resume(
        cls,
        cv_text: str,
        resume_json: dict[str, Any] | None = None,
        repo: DepartmentDomainRepository | None = None,
    ) -> list[str]:
        """
        Dynamically infers suitable job roles by scanning the candidate's actual
        work experience responsibilities, education degrees, and CV text against
        the data-driven Job Taxonomy rules and Department Domain configurations.
        """
        search_parts: list[str] = []

        if resume_json:
            for exp in resume_json.get("work_experience") or resume_json.get("experience") or []:
                if not isinstance(exp, dict):
                    continue
                if exp.get("job_title") or exp.get("title") or exp.get("position"):
                    search_parts.append(str(exp.get("job_title") or exp.get("title") or exp.get("position")))
                if exp.get("description"):
                    search_parts.append(str(exp["description"]))
                for resp in exp.get("responsibilities") or []:
                    if isinstance(resp, str):
                        search_parts.append(resp)

            for edu in resume_json.get("education") or []:
                if isinstance(edu, dict):
                    if edu.get("degree"):
                        search_parts.append(str(edu["degree"]))
                    if edu.get("field_of_study"):
                        search_parts.append(str(edu["field_of_study"]))

        if not search_parts and cv_text:
            from app.services.resume_field_extractor import ResumeFieldExtractor

            sections = ResumeFieldExtractor._split_sections(cv_text.splitlines())
            search_parts.extend(sections.get("experience", []))
            search_parts.extend(sections.get("education", []))
            search_parts.extend(sections.get("skills", []))
            search_parts.extend(sections.get("projects", []))

        search_text = " ".join(search_parts).lower()
        if not search_text.strip():
            return []

        extraction_policy = PolicyRegistry.resolve_snapshot().extraction
        scored_roles: list[tuple[int, str]] = []
        seen_roles: set[str] = set()

        repository = repo or department_domain_repository
        for matcher in repository.get_domain_matchers():
            kw_matches = matcher.keyword_match_count(search_text)
            if kw_matches >= extraction_policy.domain_keyword_min_matches:
                for role in matcher.domain.default_roles:
                    if role not in seen_roles:
                        scored_roles.append((kw_matches, role))
                        seen_roles.add(role)

        # Sort by match count descending and apply the policy result cap.
        scored_roles.sort(key=lambda x: x[0], reverse=True)
        inferred = [role for _, role in scored_roles[: extraction_policy.inferred_role_limit]]
        return cls.validate_job_roles(inferred, cv_text, resume_json, repository, taxonomy_inferred=True)

    @classmethod
    def validate_skills(
        cls,
        skills: list[str],
        cv_text: str,
        resume_json: dict[str, Any] | None = None,
        repo: DepartmentDomainRepository | None = None,
        source_confidence: float | None = None,
    ) -> list[str]:
        if source_confidence is None:
            source_confidence = PolicyRegistry.resolve_snapshot().extraction.default_skill_source_confidence
        candidates = [(skill, source_confidence) for skill in skills]
        return cls._validate_skills(candidates, cv_text, resume_json, repo or department_domain_repository)

    @classmethod
    def _has_domain_evidence(
        cls,
        domain_name: str,
        cv_text: str,
        resume_json: dict[str, Any] | None,
        repo: DepartmentDomainRepository,
    ) -> bool:
        """
        Validates if the provided canonical domain has supporting keyword evidence natively
        in the candidate's CV (roles, skills, projects).
        """
        from app.services.resume_field_extractor import ResumeFieldExtractor

        search_parts: list[str] = []

        if resume_json:
            for exp in resume_json.get("work_experience") or resume_json.get("experience") or []:
                if not isinstance(exp, dict):
                    continue
                if exp.get("job_title") or exp.get("title") or exp.get("position"):
                    search_parts.append(str(exp.get("job_title") or exp.get("title") or exp.get("position")))
                if exp.get("description"):
                    search_parts.append(str(exp["description"]))
                for resp in exp.get("responsibilities") or []:
                    if isinstance(resp, str):
                        search_parts.append(resp)

            for edu in resume_json.get("education") or []:
                if isinstance(edu, dict):
                    if edu.get("degree"):
                        search_parts.append(str(edu["degree"]))
                    if edu.get("field_of_study"):
                        search_parts.append(str(edu["field_of_study"]))
            
            skills_data = resume_json.get("skills")
            if isinstance(skills_data, dict):
                if "all_skills" in skills_data:
                    search_parts.extend(str(s) for s in skills_data["all_skills"])
                elif "categorized" in skills_data:
                    for cat, s_list in skills_data["categorized"].items():
                        if isinstance(s_list, list):
                            search_parts.extend(str(s) for s in s_list)
            elif isinstance(skills_data, list):
                search_parts.extend(str(s) for s in skills_data)

            for proj in resume_json.get("projects") or []:
                if isinstance(proj, dict):
                    if proj.get("title"):
                        search_parts.append(str(proj["title"]))
                    if proj.get("description"):
                        search_parts.append(str(proj["description"]))
                else:
                    search_parts.append(str(proj))

        if not search_parts and cv_text:
            sections = ResumeFieldExtractor._split_sections(cv_text.splitlines())
            search_parts.extend(sections.get("experience", []))
            search_parts.extend(sections.get("education", []))
            search_parts.extend(sections.get("skills", []))
            search_parts.extend(sections.get("projects", []))

        # Final fallback: use raw CV text when no structured sections found
        if not search_parts and cv_text:
            search_parts.append(cv_text)

        search_text = " ".join(search_parts).lower()
        if not search_text.strip():
            return False

        for matcher in repo.get_domain_matchers():
            if matcher.domain.domain_name == domain_name:
                # If there's at least 1 keyword match for this domain natively in the CV text, it's validated
                if matcher.keyword_match_count(search_text) > 0:
                    return True
                break

        return False

    @classmethod
    def validate_optimized_profile(
        cls,
        profile: OptimizedCandidateProfile,
        cv_text: str,
        resume_json: dict[str, Any] | None = None,
        repo: DepartmentDomainRepository | None = None,
    ) -> OptimizedCandidateProfile:
        repository = repo or department_domain_repository
        current_roles = cls.validate_job_roles(
            [profile.current_role] if profile.current_role else [], cv_text, resume_json, repository
        )
        canonical_domains = set(RuleConfigManager.get_taxonomy_rules().canonical_domains)
        professional_domains = [
            domain for domain in profile.professional_domains
            if domain in canonical_domains and cls._has_domain_evidence(domain, cv_text, resume_json, repository)
        ]
        professional_domain = profile.professional_domain
        if professional_domain not in canonical_domains or not cls._has_domain_evidence(professional_domain, cv_text, resume_json, repository):
            professional_domain = None
        return profile.model_copy(
            update={
                "core_skills": cls.validate_skills(profile.core_skills, cv_text, resume_json, repository),
                "inferred_skills": cls.validate_skills(
                    profile.inferred_skills, cv_text, resume_json, repository, source_confidence=0.35
                ),
                "current_role": current_roles[0] if current_roles else None,
                "professional_domains": professional_domains,
                "professional_domain": professional_domain,
                "suitable_job_roles": cls.validate_job_roles(
                    profile.suitable_job_roles, cv_text, resume_json, repository
                ),
            }
        )

    @classmethod
    def _validate_skills(
        cls,
        candidates: list[tuple[str, float]],
        cv_text: str,
        resume_json: dict[str, Any] | None,
        repo: DepartmentDomainRepository,
    ) -> list[str]:
        from app.services.resume_field_extractor import ResumeFieldExtractor

        sections = ResumeFieldExtractor._split_sections(cv_text.splitlines()) if cv_text else {}
        skills_text = " ".join(sections.get("skills", []))
        professional_text = " ".join(
            [*sections.get("experience", []), *sections.get("projects", []), *sections.get("education", [])]
        )
        vocabulary = cls._professional_vocabulary(repo, include_roles=False)
        accepted: list[str] = []
        seen: set[str] = set()
        for raw_value, source_score in candidates:
            value = cls._clean_entity(raw_value)
            key = value.casefold()
            if not value or key in seen or cls._is_contaminated_entity(value, resume_json):
                continue
            in_skill_section = cls._contains_entity(skills_text, value)
            in_professional_context = cls._contains_entity(professional_text, value)
            in_cv = cls._contains_entity(cv_text, value)
            if not in_cv:
                continue
            score = source_score + (0.30 if in_skill_section else 0.20 if in_professional_context else 0.10)
            score += 0.15 if cls._matches_vocabulary(value, vocabulary) else 0.0
            score += 0.05 if re.search(r"[A-Za-z]", value) and len(value.split()) <= 8 else 0.0
            if score >= cls._ENTITY_CONFIDENCE_THRESHOLD:
                seen.add(key)
                accepted.append(value)
        return accepted

    @classmethod
    def validate_job_roles(
        cls,
        roles: list[str],
        cv_text: str,
        resume_json: dict[str, Any] | None = None,
        repo: DepartmentDomainRepository | None = None,
        scored_roles: list[tuple[str, float]] | None = None,
        taxonomy_inferred: bool = False,
    ) -> list[str]:
        from app.services.resume_field_extractor import ResumeFieldExtractor

        repository = repo or department_domain_repository
        sections = ResumeFieldExtractor._split_sections(cv_text.splitlines()) if cv_text else {}
        experience_text = " ".join(sections.get("experience", []))
        occupation_vocabulary = cls._professional_vocabulary(repository, include_roles=True)
        source_scores = {cls._clean_entity(role).casefold(): score for role, score in scored_roles or []}
        accepted: list[str] = []
        seen: set[str] = set()
        for raw_role in roles:
            role = cls._clean_role(raw_role, occupation_vocabulary)
            key = role.casefold()
            if not role or key in seen or cls._is_contaminated_entity(role, resume_json):
                continue
            if ResumeFieldExtractor._DATE_RANGE.search(role) or re.search(r"\b(?:19|20)\d{2}\b", role):
                continue
            if ResumeFieldExtractor._looks_like_company(role):
                continue
            has_occupation_type = cls._matches_vocabulary(role, occupation_vocabulary, require_role=True)
            is_valid_structural_title = ResumeFieldExtractor.is_structural_job_title_noun_phrase(role)
            if not has_occupation_type and not is_valid_structural_title:
                continue
            if not ResumeFieldExtractor.is_valid_job_title(role):
                continue
            if taxonomy_inferred:
                score = 0.85
            else:
                in_experience = cls._contains_entity(experience_text, role)
                in_cv = cls._contains_entity(cv_text, role)
                if not in_cv:
                    continue
                base_score = source_scores.get(key, 0.50 if has_occupation_type else 0.40)
                boost = 0.25 if has_occupation_type else 0.15
                exp_boost = 0.20 if in_experience else 0.05
                score = base_score + boost + exp_boost
            if score >= cls._ENTITY_CONFIDENCE_THRESHOLD:
                seen.add(key)
                accepted.append(role)
        return accepted

    @classmethod
    def _professional_vocabulary(cls, repo: DepartmentDomainRepository, *, include_roles: bool) -> set[str]:
        vocabulary: set[str] = set()
        for matcher in repo.get_domain_matchers():
            if include_roles:
                vocabulary.update(cls._clean_entity(role).casefold() for role in matcher.domain.default_roles if role)
            else:
                vocabulary.update(cls._clean_entity(term.term).casefold() for term in matcher.domain.keywords if term)
        if include_roles:
            from app.services.resume_field_extractor import ResumeFieldExtractor

            vocabulary.update(term.casefold() for term in ResumeFieldExtractor.JOB_TITLE_KEYWORDS)
        else:
            assets = RuleConfigManager.get_term_matching_assets()
            for canonical, aliases in assets.get("aliases", {}).items():
                vocabulary.add(cls._clean_entity(str(canonical)).casefold())
                vocabulary.update(cls._clean_entity(str(alias)).casefold() for alias in aliases)
        return {term for term in vocabulary if term}

    @staticmethod
    def _clean_entity(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().strip("#*•|-:;,")).strip()

    @classmethod
    def _clean_role(cls, value: Any, occupation_vocabulary: set[str]) -> str:
        role = cls._clean_entity(value)
        segments = [cls._clean_entity(segment) for segment in re.split(r"\||\s+at\s+", role, flags=re.IGNORECASE)]
        occupational_segments = [segment for segment in segments if cls._matches_vocabulary(segment, occupation_vocabulary, require_role=True)]
        return occupational_segments[0] if occupational_segments else role

    @classmethod
    def _is_contaminated_entity(cls, value: str, resume_json: dict[str, Any] | None) -> bool:
        from app.services.resume_field_extractor import ResumeFieldExtractor

        normalized = value.casefold()
        compact = re.sub(r"\s+", "", normalized)
        if not normalized or value.startswith("#") or normalized in ResumeFieldExtractor.GENERIC_SECTION_HEADERS:
            return True
        if re.fullmatch(r"(?:19|20)\d{2}", value) or re.fullmatch(r"\d+(?:[./-]\d+)+", value):
            return True
        if re.fullmatch(r"[\d\s()+./-]+", value) or re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", value):
            return True
        if re.search(r"(?:https?://|www\.|linkedin\.com|github\.com)", value, re.IGNORECASE):
            return True
        match_rules = RuleConfigManager.get_match_rules()
        headings = {heading.casefold().strip() for heading in match_rules.cv_section_heading_denylist if heading}
        compact_headings = {heading.casefold().replace(" ", "").strip() for heading in match_rules.cv_section_heading_compact_denylist if heading}
        if normalized in headings or compact in compact_headings:
            return True
        contact = (resume_json or {}).get("contact_info") or {}
        personal_values = [contact.get(key) for key in ("name", "full_name", "candidate_name", "email", "phone", "location")]
        if any(normalized == cls._clean_entity(personal).casefold() for personal in personal_values if personal):
            return True
        for experience in (resume_json or {}).get("work_experience") or (resume_json or {}).get("experience") or []:
            if isinstance(experience, dict) and experience.get("company") and normalized == cls._clean_entity(experience["company"]).casefold():
                return True
        return False

    @staticmethod
    def _contains_entity(source: str, value: str) -> bool:
        normalized_source = re.sub(r"\s+", " ", source or "").casefold()
        normalized_value = re.sub(r"\s+", " ", value).casefold()
        return bool(normalized_value and normalized_value in normalized_source)

    @staticmethod
    def _matches_vocabulary(value: str, vocabulary: set[str], *, require_role: bool = False) -> bool:
        normalized = value.casefold()
        tokens = {token for token in re.split(r"[^\w+#.]+", normalized) if token}
        for term in vocabulary:
            term_tokens = {token for token in re.split(r"[^\w+#.]+", term) if token}
            if normalized == term or (require_role and term_tokens and term_tokens & tokens) or (not require_role and term in normalized):
                return True
        return False

    @classmethod
    def _extract_strengths_from_resume(
        cls,
        cv_text: str,
        resume_json: dict[str, Any] | None = None,
        prof_domain: str | None = None,
    ) -> list[str]:
        """
        Extracts meaningful strengths from resume content when no structured
        skills/education/projects are available from optimized or dynamic profiles.
        """
        strengths: list[str] = []

        if resume_json:
            # Extract education-based strengths
            for edu in resume_json.get("education") or []:
                if isinstance(edu, dict) and edu.get("degree"):
                    # Clean pipe chars from markdown table-parsed degree fields
                    degree_str = str(edu["degree"]).strip()
                    degree_str = re.sub(r"\|", " ", degree_str).strip()
                    degree_str = re.sub(r"\s+", " ", degree_str).strip()
                    # Strip trailing year fragments (e.g., "2021", "2018")
                    degree_str = re.sub(r"\s+\d{4}\s*$", "", degree_str).strip()
                    # Strip leading/trailing dashes and whitespace
                    degree_str = degree_str.strip("-").strip()
                    if len(degree_str) > 3:
                        strengths.append(f"Education: {degree_str}")
                        break

            # Extract experience-based strengths from top responsibilities
            key_responsibilities: list[str] = []
            for exp in resume_json.get("work_experience") or resume_json.get("experience") or []:
                if not isinstance(exp, dict):
                    continue
                for resp in (exp.get("responsibilities") or [])[:5]:
                    if isinstance(resp, str) and len(resp.strip()) > 15:
                        key_responsibilities.append(resp.strip())

            if key_responsibilities:
                # Summarize top 3 responsibilities as a strength
                top_resp = key_responsibilities[:3]
                strengths.append(f"Key Expertise: {'; '.join(top_resp)}")

        # Domain-based strength as fallback
        if not strengths and prof_domain:
            strengths.append(f"Professional background in {prof_domain}")

        return strengths

    @classmethod
    def _extract_cv_skill_lines(cls, cv_text: str) -> list[str]:
        from app.services.resume_field_extractor import ResumeFieldExtractor

        sections = ResumeFieldExtractor._split_sections(cv_text.splitlines())
        extracted = ResumeFieldExtractor._extract_skills(sections.get("skills", []))
        return extracted.get("all_skills", [])

    @classmethod
    def _extract_cv_role_headers(cls, cv_text: str) -> list[str]:
        from app.services.resume_field_extractor import ResumeFieldExtractor

        headers: list[str] = []
        match_rules = RuleConfigManager.get_match_rules()
        section_denylist = {h.lower().strip() for h in match_rules.cv_section_heading_denylist if h}
        compact_denylist = {h.lower().strip() for h in match_rules.cv_section_heading_compact_denylist if h}
        substring_denylist = [h.lower().strip() for h in match_rules.cv_section_heading_substring_denylist if h]

        for line_index, raw_line in enumerate(cv_text.splitlines()):
            line = raw_line.strip()
            labeled_role = re.match(r"^(?:current\s+role|job\s+title|title|designation|position)\s*:\s*(.+)$", line, re.IGNORECASE)
            header = labeled_role.group(1).strip() if labeled_role else re.sub(r"\s+", " ", line.lstrip("#-• ").strip())
            normalized_header = header.lower()
            compact_header = re.sub(r"\s+", "", normalized_header)
            if not header or normalized_header in section_denylist or compact_header in compact_denylist or any(term in normalized_header for term in substring_denylist):
                continue
            is_explicit_header = labeled_role is not None
            is_header_role = line_index < 12 and ResumeFieldExtractor.is_valid_job_title(header)
            if (is_explicit_header or is_header_role) and ResumeFieldExtractor.is_valid_job_title(header):
                headers.append(header)

        return headers

    @classmethod
    def build_domain_candidate_text(
        cls,
        cv_text: str,
        current_role: str | None = None,
        dynamic_profile: DynamicCandidateProfile | None = None,
        optimized_profile: OptimizedCandidateProfile | None = None,
        llm_match: OptimizedVacancyMatch | None = None,
        domain_repository: DepartmentDomainRepository | None = None,
    ) -> str:
        domain_parts: list[str] = []

        if current_role:
            domain_parts.append(current_role)

        if optimized_profile:
            domain_parts.extend(
                [
                    optimized_profile.current_role or "",
                    *optimized_profile.core_skills,
                    *optimized_profile.professional_domains,
                ]
            )

        if dynamic_profile:
            domain_parts.extend(
                [
                    dynamic_profile.current_role or "",
                    dynamic_profile.current_domain or "",
                    *dynamic_profile.previous_roles,
                    *dynamic_profile.core_skills,
                    *dynamic_profile.professional_domains,
                    *(event.title for event in dynamic_profile.timeline),
                ]
            )

        if llm_match:
            domain_parts.extend([*llm_match.inferred_skills, *llm_match.matched_skills])

        domain_parts.extend(cls._extract_cv_role_headers(cv_text))
        domain_parts.extend(cls._extract_cv_skill_lines(cv_text))

        domain_text = " ".join(filter(None, domain_parts)).lower()
        domain_words = set(re.findall(r"\w+", domain_text))

        repo = domain_repository or department_domain_repository
        inferred_domains = [matcher.domain.department_name for matcher in repo.get_domain_matchers() if matcher.shares_keyword_with(domain_words)]
        return " ".join([domain_text, *inferred_domains]).strip()

    @classmethod
    def extract_department_domain_terms(cls, department: str) -> list[str]:
        department_without_names = re.sub(r"\([^)]*\)", " ", department)
        denylist = {term.lower().strip() for term in RuleConfigManager.get_match_rules().domain_department_denylist if term}
        terms = []
        for token in re.split(r"[\s/&()\-,]+", department_without_names):
            term = token.strip().lower()
            if len(term) <= 2 or term in denylist:
                continue
            terms.append(term)
        return terms
