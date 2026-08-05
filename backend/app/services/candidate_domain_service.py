import re
from typing import Any

from app.core.rule_config_manager import RuleConfigManager
from app.repositories.department_domain import (
    DepartmentDomainRepository,
    department_domain_repository,
)
from app.schemas.analysis import OptimizedCandidateProfile, OptimizedVacancyMatch
from app.schemas.domain import DepartmentDomain
from app.schemas.profile import DynamicCandidateProfile
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
from app.services.job_taxonomy import TaxonomyClassifier


class CandidateDomainService:
    """
    Dedicated service for candidate domain detection, candidate text profile extraction,
    and department term resolution.
    """

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
        combined_parts = [cv_text]
        skills_set: set[str] = set()
        education_list: list[str] = []
        projects_list: list[str] = []
        roles_list: list[str] = []

        if optimized_profile:
            skills_set.update(optimized_profile.core_skills)
            skills_set.update(optimized_profile.inferred_skills)
            education_list.extend(optimized_profile.education_domains)
            if optimized_profile.current_role:
                roles_list.append(optimized_profile.current_role)
            combined_parts.extend(optimized_profile.professional_domains)

        if dynamic_profile:
            skills_set.update(dynamic_profile.core_skills)
            education_list.extend(dynamic_profile.education_domains)
            if dynamic_profile.current_role:
                roles_list.append(dynamic_profile.current_role)
            roles_list.extend(dynamic_profile.previous_roles)

        if resume_json:
            if isinstance(resume_json.get("skills"), list):
                skills_set.update(resume_json["skills"])
            elif isinstance(resume_json.get("skills"), dict):
                raw_skills = resume_json["skills"]
                if isinstance(raw_skills.get("all_skills"), list):
                    skills_set.update(s for s in raw_skills["all_skills"] if isinstance(s, str) and s.strip())
                for sub in raw_skills.values():
                    if isinstance(sub, list):
                        skills_set.update(s for s in sub if isinstance(s, str) and s.strip())
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

        combined_text = " ".join(
            filter(
                None,
                combined_parts + sorted(skills_set) + education_list + projects_list + roles_list,
            )
        ).lower()

        repo = domain_repository or department_domain_repository

        # 1. Dynamic Vector & MSSQL taxonomy resolution
        role_input = " ".join(roles_list) if roles_list else combined_text
        dyn_res = DynamicTaxonomyService.resolve_candidate_role_and_domain(
            role_or_summary=role_input,
            skills=sorted(skills_set),
        )

        if dyn_res.match_source != "legacy_fallback":
            industry_dept = dyn_res.industry_department or dyn_res.industry_domain or dyn_res.db_department_name
            prof_domain = dyn_res.industry_domain or dyn_res.db_department_name or ""
            recommended_dept = industry_dept or prof_domain
            suitable_roles = [dyn_res.db_department_name] if dyn_res.db_department_name else []
        else:
            dept_scores: list[tuple[int, DepartmentDomain]] = []
            for matcher in repo.get_domain_matchers():
                kw_matches = matcher.keyword_match_count(combined_text)
                if kw_matches > 0:
                    dept_scores.append((kw_matches, matcher.domain))

            if dept_scores:
                best_domain = max(dept_scores, key=lambda item: (item[0], -item[1].priority))[1]
                recommended_dept = best_domain.department_name
                prof_domain = best_domain.domain_name
                suitable_roles = best_domain.default_roles
            else:
                fallback_defaults = RuleConfigManager.get_match_rules().fallback_defaults
                recommended_dept = fallback_defaults.recommended_department
                prof_domain = fallback_defaults.professional_domain
                suitable_roles = list(fallback_defaults.suitable_roles)

        # Build custom roles from structured profile roles first
        custom_roles = []
        if roles_list:
            custom_roles.extend([r.title() for r in roles_list if len(r) > 2])

        # When no structured roles available, dynamically infer from actual resume content
        if not custom_roles:
            inferred = cls._infer_roles_from_resume(cv_text, resume_json, repo)
            if inferred:
                custom_roles = inferred
            else:
                custom_roles = suitable_roles

        # Build strengths from structured data first, then fall back to resume content
        strengths: list[str] = []
        if skills_set:
            top_skills = sorted(skills_set)[:5]
            strengths.append(f"Core Skills: {', '.join(top_skills)}")
        if education_list:
            strengths.append(f"Education: {', '.join(education_list[:2])}")
        if projects_list:
            strengths.append(f"Project Experience: {len(projects_list)} documented project(s)")
        if not strengths:
            strengths = cls._extract_strengths_from_resume(cv_text, resume_json, prof_domain)

        return {
            "recommended_department": recommended_dept,
            "professional_domain": prof_domain,
            "strengths": strengths,
            "suitable_job_roles": custom_roles[:4],
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
        # Build a comprehensive search text from all available resume content
        search_parts: list[str] = []
        if cv_text:
            search_parts.append(cv_text)

        if resume_json:
            for exp in resume_json.get("work_experience") or []:
                if not isinstance(exp, dict):
                    continue
                if exp.get("company"):
                    search_parts.append(str(exp["company"]))
                if exp.get("title") or exp.get("position"):
                    search_parts.append(str(exp.get("title") or exp.get("position")))
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

        search_text = " ".join(search_parts).lower()
        if not search_text.strip():
            return []

        scored_roles: list[tuple[int, str]] = []
        seen_roles: set[str] = set()

        # 1. Match using the dynamic taxonomy classifier
        _, compatible_families = TaxonomyClassifier.classify_candidate(cv_text=cv_text, resume_json=resume_json)

        # Add taxonomy families as base roles, giving them a high initial score
        for family in compatible_families:
            if family not in seen_roles and family != RuleConfigManager.get_taxonomy_rules().default_family:
                scored_roles.append((10, family))
                seen_roles.add(family)

        # 2. Match against dynamic department domains
        repository = repo or department_domain_repository
        for matcher in repository.get_domain_matchers():
            kw_matches = matcher.keyword_match_count(search_text)
            if kw_matches > 0:
                for role in matcher.domain.default_roles:
                    if role not in seen_roles:
                        scored_roles.append((kw_matches, role))
                        seen_roles.add(role)

        # Sort by match count descending and return top 4
        scored_roles.sort(key=lambda x: x[0], reverse=True)
        return [role for _, role in scored_roles[:4]]

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
            for exp in resume_json.get("work_experience") or []:
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
        if not strengths:
            fallback_defaults = RuleConfigManager.get_match_rules().fallback_defaults
            current_domain = prof_domain or fallback_defaults.professional_domain

            if current_domain != fallback_defaults.professional_domain:
                strengths.append(f"Professional background in {current_domain}")
            else:
                strengths.append(f"Broad operational background suitable for {current_domain}")

        return strengths

    @classmethod
    def _extract_cv_skill_lines(cls, cv_text: str) -> list[str]:
        skill_lines: list[str] = []
        in_skills_section = False

        for raw_line in cv_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            normalized_heading = re.sub(r"\s+", " ", line.lstrip("#- ").strip()).lower()
            compact_heading = normalized_heading.replace(" ", "")

            if compact_heading == "skills":
                in_skills_section = True
                continue

            if in_skills_section and line.startswith("##"):
                break

            if in_skills_section or re.match(r"^[\w /&+\-.#]+:\s*\S+", line):
                skill_lines.append(line)

        return skill_lines

    @classmethod
    def _extract_cv_role_headers(cls, cv_text: str) -> list[str]:
        headers: list[str] = []
        match_rules = RuleConfigManager.get_match_rules()
        section_denylist = {h.lower().strip() for h in match_rules.cv_section_heading_denylist if h}
        compact_denylist = {h.lower().strip() for h in match_rules.cv_section_heading_compact_denylist if h}
        substring_denylist = [h.lower().strip() for h in match_rules.cv_section_heading_substring_denylist if h]

        for raw_line in cv_text.splitlines():
            line = raw_line.strip()
            if not line.startswith("##"):
                continue

            header = re.sub(r"\s+", " ", line.lstrip("# ").strip())
            normalized_header = header.lower()
            compact_header = re.sub(r"\s+", "", normalized_header)
            if not header or normalized_header in section_denylist or compact_header in compact_denylist or any(term in normalized_header for term in substring_denylist):
                continue
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
                    *optimized_profile.inferred_skills,
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
