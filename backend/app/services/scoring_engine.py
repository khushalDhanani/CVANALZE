import re
from typing import Any

from app.core.config import settings
from app.repositories.job import JobRepository
from app.schemas.analysis import OptimizedCandidateProfile, OptimizedVacancyMatch
from app.schemas.match import (
    CandidateMatchAnalysis,
    DualEvidence,
    JobMatchResult,
    MandatoryFailureDetails,
    RequirementEvaluation,
    RequirementStatus,
    RequirementTier,
)
from app.schemas.profile import DynamicCandidateProfile


class ScoringEngine:
    DOMAIN_DEPARTMENT_DENYLIST = {
        "admin",
        "department",
        "development",
        "management",
        "maintenance",
        "operations",
        "service",
        "support",
        "team",
    }

    CV_SECTION_HEADING_DENYLIST = {
        "contact",
        "education",
        "languages",
        "hobbies",
        "profile summary",
        "projects",
        "skills",
        "work experience",
    }
    DEPARTMENT_DOMAIN_MAP = {
        "Information Technology & Software": {
            "keywords": [
                "developer", "engineer", "software", "flutter", "react", "frontend",
                "backend", "full stack", "fullstack", "python", "java", "javascript",
                "typescript", "dart", "c#", "dotnet", "sql", "api", "mobile", "ios",
                "android", "devops", "cloud", "aws", "azure", "docker", "kubernetes",
                "database", "ui/ux", "web", "coding", "code"
            ],
            "dept_name": "Information Technology",
            "default_roles": ["Software Developer", "Full Stack Engineer", "Frontend/Mobile Engineer", "Backend Developer"]
        },
        "Finance & Accounting": {
            "keywords": [
                "finance", "financial", "accounting", "accountant", "audit", "tax",
                "ca", "cpa", "cfa", "tally", "ledger", "payroll", "budgeting",
                "forecasting", "treasury", "billing", "valuation"
            ],
            "dept_name": "Finance & Accounting",
            "default_roles": ["Financial Analyst", "Accountant", "Finance Manager", "Audit Specialist"]
        },
        "Human Resources": {
            "keywords": [
                "hr", "human resources", "recruitment", "recruiter", "talent acquisition",
                "onboarding", "employee relations", "performance management", "hrbp",
                "payroll management", "people operations"
            ],
            "dept_name": "Human Resources",
            "default_roles": ["HR Executive", "Talent Acquisition Specialist", "HR Generalist", "Recruiter"]
        },
        "Plant & Maintenance Engineering": {
            "keywords": [
                "plant", "maintenance", "mechanical", "electrical", "utility",
                "instrumentation", "boiler", "hvac", "plc", "scada", "equipment",
                "preventive maintenance", "technician", "machinery", "fabrication"
            ],
            "dept_name": "Plant & Maintenance",
            "default_roles": ["Plant Maintenance Engineer", "Maintenance Technician", "Mechanical Engineer", "Plant Assistant"]
        },
        "Sales & Marketing": {
            "keywords": [
                "sales", "marketing", "business development", "b2b", "b2c",
                "digital marketing", "seo", "sem", "lead generation", "account management",
                "branding", "campaigns", "client relationship"
            ],
            "dept_name": "Sales & Marketing",
            "default_roles": ["Sales Executive", "Business Development Manager", "Digital Marketing Specialist", "Account Executive"]
        },
        "Quality & EHS": {
            "keywords": [
                "quality assurance", "qa", "qc", "ehs", "safety", "environmental",
                "iso", "compliance", "inspection", "audit", "safety officer", "quality control"
            ],
            "dept_name": "Quality & Safety",
            "default_roles": ["Quality Assurance Engineer", "EHS Specialist", "Quality Control Inspector"]
        },
        "Supply Chain & Operations": {
            "keywords": [
                "supply chain", "logistics", "procurement", "inventory", "warehouse",
                "store keeper", "purchase", "vendor", "distribution", "operations manager"
            ],
            "dept_name": "Supply Chain & Operations",
            "default_roles": ["Supply Chain Executive", "Logistics Coordinator", "Procurement Officer", "Operations Manager"]
        },
        "Healthcare & Clinical": {
            "keywords": [
                "clinical", "nurse", "nursing", "doctor", "physician", "patient",
                "medical", "hospital", "pharma", "pharmacist", "laboratory"
            ],
            "dept_name": "Healthcare",
            "default_roles": ["Staff Nurse", "Medical Officer", "Clinical Specialist", "Pharmacist"]
        }
    }

    @classmethod
    def extract_candidate_domain_profile(
        cls,
        cv_text: str,
        dynamic_profile: DynamicCandidateProfile | None = None,
        optimized_profile: OptimizedCandidateProfile | None = None,
        resume_json: dict[str, Any] | None = None,
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
            filter(None, combined_parts + list(skills_set) + education_list + projects_list + roles_list)
        ).lower()

        dept_scores: dict[str, float] = {}
        for cat_name, cat_info in cls.DEPARTMENT_DOMAIN_MAP.items():
            kw_matches = 0
            for kw in cat_info["keywords"]:
                if re.search(r"(?:\b|_)" + re.escape(kw) + r"(?:\b|_)", combined_text, re.IGNORECASE):
                    kw_matches += 1
            if kw_matches > 0:
                dept_scores[cat_name] = float(kw_matches)

        if dept_scores:
            best_cat_name = max(dept_scores, key=dept_scores.get)
            best_cat_info = cls.DEPARTMENT_DOMAIN_MAP[best_cat_name]
            recommended_dept = best_cat_info["dept_name"]
            prof_domain = best_cat_name
            suitable_roles = best_cat_info["default_roles"]
        else:
            recommended_dept = "General Engineering & Operations"
            prof_domain = "General Operations"
            suitable_roles = ["Operations Associate", "General Specialist"]

        custom_roles = []
        if roles_list:
            custom_roles.extend([r.title() for r in roles_list if len(r) > 2])
        if not custom_roles:
            custom_roles = suitable_roles

        strengths: list[str] = []
        if skills_set:
            top_skills = sorted(list(skills_set))[:5]
            strengths.append(f"Core Skills: {', '.join(top_skills)}")
        if education_list:
            strengths.append(f"Education: {', '.join(education_list[:2])}")
        if projects_list:
            strengths.append(f"Project Experience: {len(projects_list)} documented project(s)")
        if not strengths:
            strengths.append("Versatile background with adaptable technical & operational capabilities")

        return {
            "recommended_department": recommended_dept,
            "professional_domain": prof_domain,
            "strengths": strengths,
            "suitable_job_roles": custom_roles[:4],
        }

    @staticmethod
    def _normalize_text(text: str) -> str:
        return text.lower()

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
        for raw_line in cv_text.splitlines():
            line = raw_line.strip()
            if not line.startswith("##"):
                continue

            header = re.sub(r"\s+", " ", line.lstrip("# ").strip())
            normalized_header = header.lower()
            compact_header = re.sub(r"\s+", "", normalized_header)
            if (
                not header
                or normalized_header in cls.CV_SECTION_HEADING_DENYLIST
                or compact_header in {"skills", "workexperience"}
                or "contact" in normalized_header
                or "education" in normalized_header
                or "language" in normalized_header
            ):
                continue
            headers.append(header)

        return headers

    @classmethod
    def _build_domain_candidate_text(
        cls,
        cv_text: str,
        current_role: str | None = None,
        dynamic_profile: DynamicCandidateProfile | None = None,
        optimized_profile: OptimizedCandidateProfile | None = None,
        llm_match: OptimizedVacancyMatch | None = None,
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

        domain_text = cls._normalize_text(" ".join(filter(None, domain_parts)))
        domain_words = set(re.findall(r"\w+", domain_text))
        inferred_domains = [
            cat_info["dept_name"]
            for domain, cat_info in cls.DEPARTMENT_DOMAIN_MAP.items()
            if domain_words.intersection(set(cat_info["keywords"]))
        ]
        return " ".join([domain_text, *inferred_domains]).strip()

    @classmethod
    def _extract_department_domain_terms(cls, department: str) -> list[str]:
        department_without_names = re.sub(r"\([^)]*\)", " ", department)
        terms = []
        for token in re.split(r"[\s/&()\-,]+", department_without_names):
            term = token.strip().lower()
            if len(term) <= 2 or term in cls.DOMAIN_DEPARTMENT_DENYLIST:
                continue
            terms.append(term)
        return terms

    @classmethod
    def _extract_term_matches(
        cls, normalized_text: str, terms: list[str]
    ) -> tuple[list[str], list[str]]:
        matched = []
        missing = []

        stop_phrases = {"e.g", "eg", "e.g.", "etc", "etc.", "i.e", "i.e."}
        noise_words = {
            "programming",
            "language",
            "framework",
            "the",
            "systems",
            "principles",
            "write",
            "integrating",
            "with",
            "services",
            "backend",
            "of",
        }

        aliases: dict[str, list[str]] = {
            "widgets": ["widget", "widgets", "ui"],
            "navigation": ["navigation", "route", "routing", "maps", "gps", "eta", "directions", "places"],
            "restful apis": ["api", "apis", "rest", "restful", "http"],
            "json": ["json", "api", "apis", "data", "payload"],
            "integrating with backend services": ["backend", "api", "apis", "cloud functions", "firebase", "http"],
            "version control systems": ["git", "github", "versioning", "vcs"],
            "problem-solving": ["problem", "solving", "architecture", "logic", "clean code"],
        }


        for term in terms:
            term_clean = term.strip()
            if not term_clean:
                continue

            term_lower = term_clean.lower()
            if term_lower in stop_phrases:
                matched.append(term)
                continue

            escaped = re.escape(term_lower)
            # For special skill tokens containing symbols (+, #, .), use whitespace/delimiter boundaries
            if re.search(r"[\+\#\.]", term_clean):
                pattern = r"(?:^|[\s,;/()\-_\"\'])" + escaped + r"(?:$|[\s,;/()\-_\"\'])"
            else:
                pattern = r"(?:\b|_)" + escaped + r"(?:\b|_)"

            if re.search(pattern, normalized_text, re.IGNORECASE):
                matched.append(term)
                continue

            # Check Aliases
            if term_lower in aliases:
                alt_matched = False
                for alt in aliases[term_lower]:
                    alt_escaped = re.escape(alt)
                    if re.search(r"(?:\b|_)" + alt_escaped + r"(?:\b|_)", normalized_text, re.IGNORECASE):
                        matched.append(term)
                        alt_matched = True
                        break
                if alt_matched:
                    continue

            # Key Sub-token matching (stripping noise/filler words)
            sub_tokens = [w for w in re.split(r"[\s,;/()\-_]+", term_lower) if w and w not in noise_words and len(w) > 1]
            token_found = False
            if sub_tokens:
                for tok in sub_tokens:
                    tok_escaped = re.escape(tok)
                    if re.search(r"[\+\#\.]", tok):
                        tok_pattern = r"(?:^|[\s,;/()\-_\"\'])" + tok_escaped + r"(?:$|[\s,;/()\-_\"\'])"
                    else:
                        tok_pattern = r"(?:\b|_)" + tok_escaped + r"(?:\b|_)"
                    if re.search(tok_pattern, normalized_text, re.IGNORECASE):
                        matched.append(term)
                        token_found = True
                        break
            if token_found:
                continue

            missing.append(term)

        return matched, missing


    @classmethod
    def evaluate_job_match(
        cls, 
        cv_text: str, 
        job: dict[str, Any], 
        candidate_experience: float | None = None,
        candidate_ctc: float | None = None,
        dynamic_profile: DynamicCandidateProfile | None = None,
        optimized_profile: OptimizedCandidateProfile | None = None,
        llm_match: OptimizedVacancyMatch | None = None,
    ) -> JobMatchResult:
        from app.repositories.config import ConfigRepository
        PENALTY_PER_ITEM = float(ConfigRepository.get_setting("MANDATORY_FAILURE_PENALTY_PER_ITEM", settings.MANDATORY_FAILURE_PENALTY_PER_ITEM))
        MAX_SCORE_ON_FAILURE = float(ConfigRepository.get_setting("MAX_SCORE_ON_MANDATORY_FAILURE", settings.MAX_SCORE_ON_MANDATORY_FAILURE))
        LLM_SEMANTIC_WEIGHT = float(ConfigRepository.get_setting("LLM_SEMANTIC_WEIGHT", settings.LLM_SEMANTIC_WEIGHT))
        MAX_LLM_BOOST = float(ConfigRepository.get_setting("MAX_LLM_BOOST", settings.MAX_LLM_BOOST))
        MATCH_HIGH_THRESHOLD = float(ConfigRepository.get_setting("MATCH_HIGH_THRESHOLD", settings.MATCH_HIGH_THRESHOLD))
        MATCH_MEDIUM_THRESHOLD = float(ConfigRepository.get_setting("MATCH_MEDIUM_THRESHOLD", settings.MATCH_MEDIUM_THRESHOLD))
        
        # 1. Normalize CV & Profile Text
        profile_parts = [cv_text]
        current_role = None
        
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
            if candidate_experience is None and optimized_profile.relevant_experience_years is not None:
                candidate_experience = optimized_profile.relevant_experience_years
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
            if candidate_experience is None and dynamic_profile.relevant_experience_years is not None:
                candidate_experience = dynamic_profile.relevant_experience_years

        if not current_role:
            m = re.search(r"(?:current\s*role|position|title)\s*:\s*([^\n]+)", cv_text, re.IGNORECASE)
            if m:
                current_role = m.group(1).strip()
            else:
                m_header = re.search(r"##\s*([^\n]+)", cv_text)
                if m_header:
                    current_role = m_header.group(1).strip()

        norm_text = cls._normalize_text(" ".join(filter(None, profile_parts)))


        # 2. Extract Requirement Categories
        req_skills = job.get("required_skills", [])
        pref_keywords = job.get("preferred_keywords", [])
        min_exp = job.get("min_experience_years")
        max_exp = job.get("max_experience_years")
        max_ctc = job.get("max_ctc")
        education_req = job.get("education_requirements") or job.get("required_education")
        certification_req = job.get("certifications") or job.get("required_certifications")

        mandatory_reqs: list[RequirementEvaluation] = []
        preferred_reqs: list[RequirementEvaluation] = []
        optional_reqs: list[RequirementEvaluation] = []
        mandatory_failures: list[MandatoryFailureDetails] = []
        matched_criteria: list[str] = []
        missing_criteria: list[str] = []
        evidence_map: dict[str, DualEvidence] = {}

        # 3. Evaluate Mandatory Skills
        matched_skills, missing_skills = cls._extract_term_matches(norm_text, req_skills)
        if llm_match and llm_match.matched_skills:
            for ms in llm_match.matched_skills:
                if ms not in matched_skills:
                    matched_skills.append(ms)
                if ms in missing_skills:
                    missing_skills.remove(ms)

        for skill in req_skills:
            req_id = f"req_skill_{skill.lower().replace(' ', '_')}"
            vac_ev = f"Mandatory Skill Requirement: {skill}"
            if skill in matched_skills:
                cv_ev = f"CV contains skill: '{skill}'"
                ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                mandatory_reqs.append(RequirementEvaluation(
                    requirement_id=req_id,
                    description=f"Skill: {skill}",
                    tier=RequirementTier.MANDATORY,
                    status=RequirementStatus.SATISFIED,
                    evidence=ev
                ))
                evidence_map[req_id] = ev
                matched_criteria.append(f"Mandatory Skill: {skill}")
            else:
                cv_ev = f"CV missing explicit mention of skill: '{skill}'"
                ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                reason_str = f"Mandatory skill '{skill}' is not present in CV."
                mandatory_reqs.append(RequirementEvaluation(
                    requirement_id=req_id,
                    description=f"Skill: {skill}",
                    tier=RequirementTier.MANDATORY,
                    status=RequirementStatus.FAILED,
                    evidence=ev,
                    failure_reason=reason_str
                ))
                evidence_map[req_id] = ev
                missing_criteria.append(f"Mandatory Skill: {skill}")
                mandatory_failures.append(MandatoryFailureDetails(
                    requirement_id=req_id,
                    description=f"Skill: {skill}",
                    reason=reason_str,
                    score_impact=PENALTY_PER_ITEM
                ))

        # 4. Evaluate Mandatory Minimum Experience
        if min_exp is not None:
            req_id = "req_min_experience"
            vac_ev = f"Mandatory Minimum Experience: {min_exp} years"
            if candidate_experience is not None:
                if candidate_experience >= min_exp:
                    cv_ev = f"Candidate has {candidate_experience} years of experience (meets mandatory {min_exp} years)"
                    ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                    mandatory_reqs.append(RequirementEvaluation(
                        requirement_id=req_id,
                        description=f"Minimum Experience: {min_exp} years",
                        tier=RequirementTier.MANDATORY,
                        status=RequirementStatus.SATISFIED,
                        evidence=ev
                    ))
                    evidence_map[req_id] = ev
                    matched_criteria.append(f"Minimum Experience ({min_exp} years)")
                else:
                    cv_ev = f"Candidate has {candidate_experience} years of experience (below mandatory {min_exp} years)"
                    ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                    reason_str = f"Candidate experience ({candidate_experience} yrs) is below mandatory minimum ({min_exp} yrs)."
                    mandatory_reqs.append(RequirementEvaluation(
                        requirement_id=req_id,
                        description=f"Minimum Experience: {min_exp} years",
                        tier=RequirementTier.MANDATORY,
                        status=RequirementStatus.FAILED,
                        evidence=ev,
                        failure_reason=reason_str
                    ))
                    evidence_map[req_id] = ev
                    missing_criteria.append(f"Minimum Experience ({min_exp} years)")
                    mandatory_failures.append(MandatoryFailureDetails(
                        requirement_id=req_id,
                        description=f"Minimum Experience: {min_exp} years",
                        reason=reason_str,
                        score_impact=PENALTY_PER_ITEM
                    ))

        # 5. Evaluate Mandatory Education (ONLY if explicitly specified in vacancy)
        if education_req:
            req_id = "req_education"
            vac_ev = f"Mandatory Education Requirement: {education_req}"
            edu_matched, _ = cls._extract_term_matches(norm_text, [str(education_req)])
            if edu_matched or (optimized_profile and optimized_profile.education_domains):
                cv_ev = f"CV contains education matching '{education_req}'"
                ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                mandatory_reqs.append(RequirementEvaluation(
                    requirement_id=req_id,
                    description=f"Education: {education_req}",
                    tier=RequirementTier.MANDATORY,
                    status=RequirementStatus.SATISFIED,
                    evidence=ev
                ))
                evidence_map[req_id] = ev
                matched_criteria.append(f"Education ({education_req})")
            else:
                cv_ev = f"CV does not show required education '{education_req}'"
                ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                reason_str = f"Mandatory education '{education_req}' not found in CV."
                mandatory_reqs.append(RequirementEvaluation(
                    requirement_id=req_id,
                    description=f"Education: {education_req}",
                    tier=RequirementTier.MANDATORY,
                    status=RequirementStatus.FAILED,
                    evidence=ev,
                    failure_reason=reason_str
                ))
                evidence_map[req_id] = ev
                missing_criteria.append(f"Education ({education_req})")
                mandatory_failures.append(MandatoryFailureDetails(
                    requirement_id=req_id,
                    description=f"Education: {education_req}",
                    reason=reason_str,
                    score_impact=PENALTY_PER_ITEM
                ))

        # 6. Evaluate Mandatory Certification (ONLY if explicitly specified in vacancy)
        if certification_req:
            req_id = "req_certification"
            vac_ev = f"Mandatory Certification Requirement: {certification_req}"
            cert_matched, _ = cls._extract_term_matches(norm_text, [str(certification_req)])
            if cert_matched or (optimized_profile and optimized_profile.certifications):
                cv_ev = f"CV contains certification matching '{certification_req}'"
                ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                mandatory_reqs.append(RequirementEvaluation(
                    requirement_id=req_id,
                    description=f"Certification: {certification_req}",
                    tier=RequirementTier.MANDATORY,
                    status=RequirementStatus.SATISFIED,
                    evidence=ev
                ))
                evidence_map[req_id] = ev
                matched_criteria.append(f"Certification ({certification_req})")
            else:
                cv_ev = f"CV does not show required certification '{certification_req}'"
                ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                reason_str = f"Mandatory certification '{certification_req}' not found in CV."
                mandatory_reqs.append(RequirementEvaluation(
                    requirement_id=req_id,
                    description=f"Certification: {certification_req}",
                    tier=RequirementTier.MANDATORY,
                    status=RequirementStatus.FAILED,
                    evidence=ev,
                    failure_reason=reason_str
                ))
                evidence_map[req_id] = ev
                missing_criteria.append(f"Certification ({certification_req})")
                mandatory_failures.append(MandatoryFailureDetails(
                    requirement_id=req_id,
                    description=f"Certification: {certification_req}",
                    reason=reason_str,
                    score_impact=PENALTY_PER_ITEM
                ))

        # 7. Evaluate Mandatory CTC Budget (if specified)
        if candidate_ctc is not None and max_ctc is not None:
            if candidate_ctc > max_ctc:
                req_id = "req_max_ctc"
                vac_ev = f"Mandatory Maximum Budget CTC: {max_ctc}"
                cv_ev = f"Candidate CTC expectation ({candidate_ctc}) exceeds budget max ({max_ctc})"
                ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                reason_str = f"Candidate CTC ({candidate_ctc}) exceeds vacancy maximum budget ({max_ctc})."
                mandatory_reqs.append(RequirementEvaluation(
                    requirement_id=req_id,
                    description=f"Max CTC Budget: {max_ctc}",
                    tier=RequirementTier.MANDATORY,
                    status=RequirementStatus.FAILED,
                    evidence=ev,
                    failure_reason=reason_str
                ))
                evidence_map[req_id] = ev
                missing_criteria.append(f"CTC Budget (Exceeds max {max_ctc})")
                mandatory_failures.append(MandatoryFailureDetails(
                    requirement_id=req_id,
                    description=f"Max CTC Budget: {max_ctc}",
                    reason=reason_str,
                    score_impact=PENALTY_PER_ITEM
                ))

        # 8. Evaluate Preferred Keywords
        matched_keywords, missing_keywords = cls._extract_term_matches(norm_text, pref_keywords)
        for kw in pref_keywords:
            req_id = f"pref_keyword_{kw.lower().replace(' ', '_')}"
            vac_ev = f"Preferred Keyword: {kw}"
            if kw in matched_keywords:
                cv_ev = f"CV mentions preferred keyword: '{kw}'"
                ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                preferred_reqs.append(RequirementEvaluation(
                    requirement_id=req_id,
                    description=f"Preferred Keyword: {kw}",
                    tier=RequirementTier.PREFERRED,
                    status=RequirementStatus.SATISFIED,
                    evidence=ev
                ))
                evidence_map[req_id] = ev
                matched_criteria.append(f"Preferred Keyword: {kw}")
            else:
                cv_ev = f"CV missing preferred keyword: '{kw}'"
                ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                preferred_reqs.append(RequirementEvaluation(
                    requirement_id=req_id,
                    description=f"Preferred Keyword: {kw}",
                    tier=RequirementTier.PREFERRED,
                    status=RequirementStatus.FAILED,
                    evidence=ev,
                    failure_reason=f"Preferred keyword '{kw}' not mentioned in CV."
                ))
                evidence_map[req_id] = ev
                missing_criteria.append(f"Preferred Keyword: {kw}")

        # 9. Evaluate Preferred Maximum Experience
        if max_exp is not None:
            req_id = "pref_max_experience"
            vac_ev = f"Preferred Upper Bound Experience: {max_exp} years"
            if candidate_experience is not None:
                if candidate_experience <= max_exp:
                    cv_ev = f"Candidate experience {candidate_experience} years is within preferred upper bound ({max_exp} years)"
                    ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                    preferred_reqs.append(RequirementEvaluation(
                        requirement_id=req_id,
                        description=f"Max Experience: {max_exp} years",
                        tier=RequirementTier.PREFERRED,
                        status=RequirementStatus.SATISFIED,
                        evidence=ev
                    ))
                    evidence_map[req_id] = ev
                    matched_criteria.append(f"Max Experience ({max_exp} years)")
                else:
                    cv_ev = f"Candidate experience {candidate_experience} years exceeds preferred upper bound ({max_exp} years)"
                    ev = DualEvidence(cv_evidence=cv_ev, vacancy_evidence=vac_ev)
                    preferred_reqs.append(RequirementEvaluation(
                        requirement_id=req_id,
                        description=f"Max Experience: {max_exp} years",
                        tier=RequirementTier.PREFERRED,
                        status=RequirementStatus.PARTIALLY_SATISFIED,
                        evidence=ev,
                        failure_reason=f"Candidate experience exceeds preferred upper limit ({max_exp} years)."
                    ))
                    evidence_map[req_id] = ev

        # 10. Dynamic Career Transition Detection
        job_title = job.get("title", "")
        career_transition_detected = False
        career_transition_note = None

        if current_role and job_title:
            current_clean = current_role.strip().lower()
            job_clean = job_title.strip().lower()
            # Simple term divergence check for career transition
            current_words = set(re.findall(r"\w+", current_clean))
            job_words = set(re.findall(r"\w+", job_clean))
            common_words = current_words.intersection(job_words) - {"senior", "junior", "lead", "head", "manager", "developer", "engineer", "specialist"}
            if not common_words and current_clean != job_clean:
                career_transition_detected = True
                career_transition_note = f"Dynamic career transition detected: Current role '{current_role}' to Target role '{job_title}'."
                if llm_match and llm_match.career_transition_note:
                    career_transition_note += f" LLM analysis: {llm_match.career_transition_note}"

        # 11. Deterministic Multi-Dimensional Score Calculation

        # Role Score
        role_score = 100.0
        if career_transition_detected:
            role_score = 50.0
        elif current_role and job_title:
            current_clean = current_role.strip().lower()
            job_clean = job_title.strip().lower()
            if current_clean != job_clean and not common_words:
                role_score = 70.0

        # Skills Score
        total_skills = len(req_skills) + len(pref_keywords)
        matched_total_skills = len(matched_skills) + len(matched_keywords)
        skills_score = None
        if total_skills > 0:
            skills_score = (matched_total_skills / total_skills) * 100.0

        # Experience Score
        experience_score = None
        if min_exp is not None or max_exp is not None:
            experience_score = 100.0
            if min_exp is not None and candidate_experience is not None:
                if candidate_experience < min_exp:
                    experience_score = (candidate_experience / min_exp) * 50.0  # Cap at 50% if below min
            if max_exp is not None and candidate_experience is not None:
                if candidate_experience > max_exp:
                    experience_score -= 20.0  # Penalty for overqualification
            experience_score = max(0.0, min(100.0, experience_score))

        # Education Score
        education_score = None
        if education_req:
            education_score = 100.0
            edu_matched, _ = cls._extract_term_matches(norm_text, [str(education_req)])
            if not edu_matched and not (optimized_profile and optimized_profile.education_domains):
                education_score = 0.0

        # Certification Score
        certification_score = None
        if certification_req:
            certification_score = 100.0
            cert_matched, _ = cls._extract_term_matches(norm_text, [str(certification_req)])
            if not cert_matched and not (optimized_profile and optimized_profile.certifications):
                certification_score = 0.0

        # Domain Score
        domain_score = None
        job_department = job.get("department_name") or job.get("department") or ""
        if job_department:
            domain_score = 50.0
            dept_terms = cls._extract_department_domain_terms(job_department)
            domain_candidate_text = cls._build_domain_candidate_text(
                cv_text=cv_text,
                current_role=current_role,
                dynamic_profile=dynamic_profile,
                optimized_profile=optimized_profile,
                llm_match=llm_match,
            )
            if dept_terms:
                matched_dept_terms = []
                for term in dept_terms:
                    if re.search(r"\b" + re.escape(term) + r"\b", domain_candidate_text, re.IGNORECASE):
                        matched_dept_terms.append(term)
                if matched_dept_terms:
                    domain_score = 100.0

        # Technology Score
        technology_score = None
        tech_reqs = job.get("technologies", [])
        if tech_reqs:
            tech_matched, _ = cls._extract_term_matches(norm_text, tech_reqs)
            technology_score = (len(tech_matched) / len(tech_reqs)) * 100.0

        # Responsibilities Score
        responsibilities_score = None
        resp_reqs = job.get("responsibilities", [])
        if resp_reqs:
            resp_matched, _ = cls._extract_term_matches(norm_text, resp_reqs)
            responsibilities_score = (len(resp_matched) / len(resp_reqs)) * 100.0


        # Calculate Overall Raw Score (Weighted)
        weights = ConfigRepository.get_setting("MATCH_COMPONENT_WEIGHTS", {
            "role": 0.15,
            "skills": 0.25,
            "experience": 0.15,
            "education": 0.10,
            "domain": 0.15,
            "technology": 0.10,
            "certification": 0.05,
            "responsibilities": 0.05
        })

        active_weights = 0.0
        weighted_sum = 0.0
        
        scores_map = {
            "role": (role_score, weights["role"]),
            "skills": (skills_score, weights["skills"]),
            "experience": (experience_score, weights["experience"]),
            "education": (education_score, weights["education"]),
            "domain": (domain_score, weights["domain"]),
            "technology": (technology_score, weights["technology"]),
            "certification": (certification_score, weights["certification"]),
            "responsibilities": (responsibilities_score, weights["responsibilities"])
        }
        
        for name, (score_val, weight) in scores_map.items():
            if score_val is not None:
                weighted_sum += (score_val * weight)
                active_weights += weight
                
        raw_score = (weighted_sum / active_weights) if active_weights > 0 else 0.0
        coverage = active_weights / sum(weights.values())
        
        llm_boost = 0.0
        if llm_match and llm_match.semantic_fit_score:
            llm_boost = min(MAX_LLM_BOOST, llm_match.semantic_fit_score * LLM_SEMANTIC_WEIGHT)
            
        raw_score += llm_boost

        if mandatory_failures:
            total_penalty = len(mandatory_failures) * PENALTY_PER_ITEM
            final_score = round(max(0.0, min(raw_score - total_penalty, MAX_SCORE_ON_FAILURE)), 1)
            hr_review_required = True
            reason_str = "Mandatory requirement failure(s): " + "; ".join(f"{f.description} ({f.reason})" for f in mandatory_failures)
        else:
            final_score = round(min(100.0, max(0.0, raw_score)), 1)
            # STRICT FALSE 100% GUARD
            if final_score >= 100.0:
                if (skills_score is not None and skills_score < 100.0) or len(missing_criteria) > 0 or (domain_score is not None and domain_score < 100.0):
                    final_score = 99.0
            hr_review_required = (final_score < MATCH_HIGH_THRESHOLD)
            reason_str = f"All mandatory requirements satisfied. Overall match score is {final_score}%."

        # Cross-Domain Divergence Guard:
        # Prevent candidate domain mismatches (e.g. software candidates scoring high on non-IT roles, or finance candidates scoring high on software roles)
        cand_profile = cls.extract_candidate_domain_profile(
            cv_text=cv_text,
            dynamic_profile=dynamic_profile,
            optimized_profile=optimized_profile,
        )
        cand_dept = cand_profile.get("recommended_department", "")
        cand_domain = cand_profile.get("professional_domain", "")

        is_software_cand = (
            "Information Technology" in cand_dept
            or "Software" in cand_domain
            or any(
                k in norm_text
                for k in [
                    "flutter developer",
                    "sr developer",
                    "full stack developer",
                    "software developer",
                    "software engineer",
                    "mobile developer",
                    "dart",
                    "react native",
                ]
            )
        )
        is_non_it_job = any(
            k in job_title.lower() or k in job_department.lower()
            for k in [
                "plant",
                "chemist",
                "cafe",
                "fire",
                "store",
                "safety",
                "maintenance",
                "utility",
                "ehs",
                "production",
                "hr",
                "human resources",
                "finance",
                "accounting",
            ]
        )
        has_software_req = any(
            "software" in str(s).lower()
            or "developer" in str(s).lower()
            or "code" in str(s).lower()
            or "dotnet" in str(s).lower()
            or "flutter" in str(s).lower()
            for s in req_skills
        )

        domain_mismatch = False
        if is_software_cand and is_non_it_job and not has_software_req:
            domain_mismatch = True
        elif cand_dept and job_department:
            job_dept_clean = job_department.lower()
            if "information technology" in cand_dept.lower() and not any(
                w in job_dept_clean or w in job_title.lower()
                for w in ["software", "it", "tech", "developer", "data", "system", "code", "web"]
            ):
                domain_mismatch = True
            elif "finance" in cand_dept.lower() and not any(
                w in job_dept_clean or w in job_title.lower()
                for w in ["finance", "account", "audit", "tax", "ledger"]
            ):
                domain_mismatch = True
            elif "human resources" in cand_dept.lower() and not any(
                w in job_dept_clean or w in job_title.lower()
                for w in ["hr", "human", "recruit", "people", "talent"]
            ):
                domain_mismatch = True

        if domain_mismatch:
            domain_score = 0.0
            final_score = round(max(0.0, min(final_score * 0.15, 20.0)), 1)
            reason_str += f" | Strict Domain Mismatch Penalty: Candidate domain ({cand_dept}) conflicts with job department ({job_department})."
            if not any(f.requirement_id == "req_domain_mismatch" for f in mandatory_failures):
                mandatory_failures.append(
                    MandatoryFailureDetails(
                        requirement_id="req_domain_mismatch",
                        description=f"Domain Mismatch: Candidate domain ({cand_dept}) conflicts with vacancy department ({job_department})",
                        reason=f"Candidate background ({cand_domain}) does not match job opening domain ({job_department}).",
                        score_impact=50.0,
                    )
                )

        if coverage < 0.5:
            classification = "LOW"
            recommendation = "Low Confidence Match — Requires HR verification (Vacancy is underspecified)."

        elif final_score >= MATCH_HIGH_THRESHOLD:
            classification = "HIGH"
            recommendation = "Strong candidate — proceed to interview."
        elif final_score >= MATCH_MEDIUM_THRESHOLD:
            classification = "MEDIUM"
            recommendation = "Potential match — HR review recommended."
        else:
            classification = "LOW"
            recommendation = "Significant requirements missing — Manual HR review required (never auto-rejected)."

        total_req_count = len(mandatory_reqs) + len(preferred_reqs) + len(optional_reqs)
        evidence_count = len(evidence_map)
        confidence_val = round(evidence_count / total_req_count, 2) if total_req_count > 0 else 1.0

        if coverage < 0.5:
            missing_criteria.append("LOW_COVERAGE: Vacancy has poorly defined requirements.")
            reason_str = f"{reason_str} | Note: Low match coverage ({int(coverage*100)}%)."
            
        def safe_round(val):
            return round(val, 1) if val is not None else 0.0

        return JobMatchResult(
            job_id=str(job.get("id") or job.get("vacancy_id")),
            job_title=job["title"],
            department=job["department"],
            vacancy_id=job.get("vacancy_id"),
            job_profile_id=job.get("job_profile_id"),
            company_id=job.get("company_id"),
            department_id=job.get("department_id"),
            department_name=job.get("department_name") or job.get("department"),
            location_id=job.get("location_id"),
            score=final_score,
            overall_score=final_score,
            role_score=safe_round(role_score),
            skills_score=safe_round(skills_score),
            experience_score=safe_round(experience_score),
            education_score=safe_round(education_score),
            domain_score=safe_round(domain_score),
            technology_score=safe_round(technology_score),
            certification_score=safe_round(certification_score),
            responsibilities_score=safe_round(responsibilities_score),
            coverage=round(coverage, 2),
            ranking_reason="",
            classification=classification,
            recommendation=recommendation,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            mandatory_requirements=mandatory_reqs,
            preferred_requirements=preferred_reqs,
            optional_requirements=optional_reqs,
            matched_criteria=matched_criteria,
            missing_criteria=missing_criteria,
            evidence=evidence_map,
            mandatory_failures=mandatory_failures,
            confidence=confidence_val,
            hr_review_required=hr_review_required,
            reason=reason_str,
            career_transition_detected=career_transition_detected,
            career_transition_note=career_transition_note,
        )


    @classmethod
    def analyze_cv(
        cls,
        cv_text: str,
        job_openings: list[dict[str, Any]] | None = None,
        dynamic_profile: DynamicCandidateProfile | None = None,
    ) -> CandidateMatchAnalysis:
        openings = (
            job_openings if job_openings is not None else JobRepository.get_all_jobs()
        )

        evaluated_matches = [
            cls.evaluate_job_match(cv_text, job, dynamic_profile=dynamic_profile)
            for job in openings
        ]

        evaluated_matches.sort(key=lambda m: m.score, reverse=True)

        best_match = (
            evaluated_matches[0]
            if evaluated_matches
            else JobMatchResult(
                job_id="general",
                job_title="General Role",
                department="General",
                score=0.0,
                classification="LOW",
                recommendation="HR review required.",
                matched_skills=[],
                missing_skills=[],
                matched_keywords=[],
                missing_keywords=[],
            )
        )

        return CandidateMatchAnalysis(
            primary_department=best_match.department,
            best_match=best_match,
            suitable_openings=evaluated_matches,
        )
