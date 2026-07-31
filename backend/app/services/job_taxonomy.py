import re
from typing import Any
from pydantic import BaseModel, Field


class TaxonomyNode(BaseModel):
    department: str
    domain: str
    job_family: str
    keywords: list[str] = Field(default_factory=list)


class JobTaxonomy:
    """
    4-Tier Enterprise Job Taxonomy: Department -> Domain -> Job Family -> Vacancy.
    """

    # Canonical Domains
    DOMAIN_IT_SOFTWARE = "IT & Software Services"
    DOMAIN_PLANT_OPERATIONS = "Plant Operations & Maintenance"
    DOMAIN_QUALITY_LAB = "Quality Assurance & QC Laboratory"
    DOMAIN_EHS_ENVIRONMENT = "Environmental Health & Safety (EHS)"
    DOMAIN_PROCESS_PROJECT = "Process & Project Engineering"
    DOMAIN_FINANCE_ADMIN = "Finance & Administration"
    DOMAIN_OTHER = "General Operations"

    # Canonical Job Families
    FAMILY_SOFTWARE_DEV = "Software Engineering & Development"
    FAMILY_IT_NETWORKING_AV = "IT Infrastructure, Networking & AV Systems"
    FAMILY_PLANT_ELECTRICAL = "Plant Electrical & Utility Maintenance"
    FAMILY_CONTROL_INSTRUMENTATION = "Control & Instrumentation (C&I)"
    FAMILY_QC_LAB = "Quality Control (QC) & Laboratory"
    FAMILY_QA_ASSURANCE = "Quality Assurance (QA)"
    FAMILY_FIRE_SAFETY = "Fire, Safety & EHS"
    FAMILY_PROCESS_PROJECT = "Process & Project Engineering"
    FAMILY_ENVIRONMENT_ETP = "Environment & ETP Operations"
    FAMILY_FINANCE_ADMIN = "Finance & Administration"
    FAMILY_OTHER = "General Professional"

    # Job Family Compatibility Matrix
    # Dict mapping candidate_family -> set of compatible job_families
    COMPATIBILITY_MAP: dict[str, set[str]] = {
        FAMILY_SOFTWARE_DEV: {FAMILY_SOFTWARE_DEV, FAMILY_IT_NETWORKING_AV},
        FAMILY_IT_NETWORKING_AV: {FAMILY_IT_NETWORKING_AV, FAMILY_SOFTWARE_DEV},
        FAMILY_PLANT_ELECTRICAL: {FAMILY_PLANT_ELECTRICAL, FAMILY_CONTROL_INSTRUMENTATION},
        FAMILY_CONTROL_INSTRUMENTATION: {FAMILY_CONTROL_INSTRUMENTATION, FAMILY_PLANT_ELECTRICAL},
        FAMILY_QC_LAB: {FAMILY_QC_LAB, FAMILY_QA_ASSURANCE, FAMILY_PROCESS_PROJECT},
        FAMILY_QA_ASSURANCE: {FAMILY_QA_ASSURANCE, FAMILY_QC_LAB},
        FAMILY_FIRE_SAFETY: {FAMILY_FIRE_SAFETY, FAMILY_ENVIRONMENT_ETP},
        FAMILY_ENVIRONMENT_ETP: {FAMILY_ENVIRONMENT_ETP, FAMILY_FIRE_SAFETY, FAMILY_PROCESS_PROJECT},
        FAMILY_PROCESS_PROJECT: {FAMILY_PROCESS_PROJECT, FAMILY_QC_LAB, FAMILY_ENVIRONMENT_ETP},
        FAMILY_FINANCE_ADMIN: {FAMILY_FINANCE_ADMIN},
        FAMILY_OTHER: {FAMILY_OTHER},
    }


class TaxonomyClassifier:
    """
    Classifier for categorizing vacancies and candidate CVs into the 4-tier Job Taxonomy.
    """

    @classmethod
    def classify_vacancy(cls, job: dict[str, Any]) -> tuple[str, str]:
        """
        Classifies a job opening into (domain, job_family).
        """
        title = str(job.get("title") or "").lower()
        dept = str(job.get("department_name") or job.get("department") or "").lower()
        desc = str(job.get("job_description") or job.get("description") or "").lower()
        req_skills = " ".join(str(s).lower() for s in job.get("required_skills", []))
        full_text = f"{title} {dept} {desc} {req_skills}"

        # 1. Software Engineering
        if any(w in title for w in ["software", "developer", ".net", "flutter", "full stack", "react", "backend", "frontend", "coder", "programmer"]):
            return (JobTaxonomy.DOMAIN_IT_SOFTWARE, JobTaxonomy.FAMILY_SOFTWARE_DEV)
        if "cis team" in dept and not any(w in title for w in ["network", "system admin", "helpdesk"]):
            return (JobTaxonomy.DOMAIN_IT_SOFTWARE, JobTaxonomy.FAMILY_SOFTWARE_DEV)

        # 2. IT Infrastructure, Networking & AV Systems
        if any(w in full_text for w in ["network", "system admin", "sysadmin", "infrastructure", "av ", "audio visual", "cisco", "switch", "router", "helpdesk", "desktop support", "it support"]):
            if "information technology" in dept or "it " in dept or "cis team" in dept or "support" in dept or "technical support" in dept:
                return (JobTaxonomy.DOMAIN_IT_SOFTWARE, JobTaxonomy.FAMILY_IT_NETWORKING_AV)
            if any(w in title for w in ["network", "systems administrator", "support technician", "it officer"]):
                return (JobTaxonomy.DOMAIN_IT_SOFTWARE, JobTaxonomy.FAMILY_IT_NETWORKING_AV)

        # 3. Plant Electrical & Utility Maintenance
        if "electrical" in full_text or "utility" in full_text or "substation" in full_text or "power" in full_text:
            if any(w in full_text for w in ["plant", "maintenance", "transformer", "switchgear", "panel", "high voltage", "ht/lt"]):
                return (JobTaxonomy.DOMAIN_PLANT_OPERATIONS, JobTaxonomy.FAMILY_PLANT_ELECTRICAL)

        # 4. Control & Instrumentation (C&I)
        if "instrumentation" in full_text or "c&i" in full_text or "scada" in full_text or "plc" in full_text or "dcs" in full_text:
            return (JobTaxonomy.DOMAIN_PLANT_OPERATIONS, JobTaxonomy.FAMILY_CONTROL_INSTRUMENTATION)

        # 5. Quality Control (QC) & Lab
        if "qc" in title or "quality control" in full_text or "lab assistant" in title or "chemist" in title or "laboratory" in full_text:
            return (JobTaxonomy.DOMAIN_QUALITY_LAB, JobTaxonomy.FAMILY_QC_LAB)

        # 6. Quality Assurance (QA)
        if "qa" in title or "quality assurance" in full_text or "iso auditor" in title:
            return (JobTaxonomy.DOMAIN_QUALITY_LAB, JobTaxonomy.FAMILY_QA_ASSURANCE)

        # 7. Fire, Safety & EHS
        if "safety" in title or "ehs" in full_text or "fire marshal" in title or "fire officer" in title or "safety officer" in title:
            return (JobTaxonomy.DOMAIN_EHS_ENVIRONMENT, JobTaxonomy.FAMILY_FIRE_SAFETY)

        # 8. Environment & ETP Operations
        if "etp" in title or "environment" in dept or "water treatment" in full_text or "mee" in title:
            return (JobTaxonomy.DOMAIN_EHS_ENVIRONMENT, JobTaxonomy.FAMILY_ENVIRONMENT_ETP)

        # 9. Process & Project Engineering
        if "process" in title or "project" in title or "chemical" in full_text or "plant operations" in dept:
            return (JobTaxonomy.DOMAIN_PROCESS_PROJECT, JobTaxonomy.FAMILY_PROCESS_PROJECT)

        # 10. Maintenance general
        if "maintenance" in dept or "maintenance" in title:
            return (JobTaxonomy.DOMAIN_PLANT_OPERATIONS, JobTaxonomy.FAMILY_PLANT_ELECTRICAL)

        # 11. Finance & Administration
        if any(w in dept or w in title for w in ["finance", "accounting", "hr", "human resources", "admin"]):
            return (JobTaxonomy.DOMAIN_FINANCE_ADMIN, JobTaxonomy.FAMILY_FINANCE_ADMIN)

        # Default fallback by Department
        if "information technology" in dept or "cis" in dept:
            return (JobTaxonomy.DOMAIN_IT_SOFTWARE, JobTaxonomy.FAMILY_IT_NETWORKING_AV)
        if "maintenance" in dept or "electrical" in dept:
            return (JobTaxonomy.DOMAIN_PLANT_OPERATIONS, JobTaxonomy.FAMILY_PLANT_ELECTRICAL)

        return (JobTaxonomy.DOMAIN_OTHER, JobTaxonomy.FAMILY_OTHER)

    @classmethod
    def classify_candidate(cls, cv_text: str, resume_json: dict[str, Any] | None = None) -> tuple[str, list[str]]:
        """
        Classifies candidate CV text into primary domain and list of compatible job families.
        """
        text_lower = cv_text.lower()

        # Check resume_json if available
        summary = ""
        exp_titles = ""
        skills_str = ""
        edu_str = ""
        if resume_json and isinstance(resume_json, dict):
            summary = str(resume_json.get("summary") or "").lower()
            exp_list = resume_json.get("experience", [])
            if isinstance(exp_list, list):
                exp_titles = " ".join(str(e.get("title") or "").lower() for e in exp_list if isinstance(e, dict))
            skills_data = resume_json.get("skills")
            if isinstance(skills_data, list):
                skills_str = " ".join(str(s).lower() for s in skills_data)
            elif isinstance(skills_data, dict):
                skills_str = " ".join(str(s).lower() for s in skills_data.keys())
            edu_list = resume_json.get("education", [])
            if isinstance(edu_list, list):
                edu_str = " ".join(str(e).lower() for e in edu_list)

        candidate_full_text = f"{text_lower} {summary} {exp_titles} {skills_str} {edu_str}"

        # 1. Software Developer Candidate
        is_software = any(
            w in candidate_full_text for w in [
                "software developer", "software engineer", "full stack developer",
                "frontend developer", "backend developer", ".net developer", "flutter developer",
                "python developer", "react developer", "node.js developer"
            ]
        )
        if is_software:
            return (
                JobTaxonomy.DOMAIN_IT_SOFTWARE,
                [JobTaxonomy.FAMILY_SOFTWARE_DEV, JobTaxonomy.FAMILY_IT_NETWORKING_AV]
            )

        # 2. IT Infrastructure, Networking & AV Candidate
        is_it_networking_av = any(
            w in candidate_full_text for w in [
                "audio visual", "av & networking", "av engineer", "av technician",
                "network engineer", "systems administrator", "sysadmin", "desktop support",
                "helpdesk", "cisco", "routers", "switches", "vlan", "dante", "crestron", "q-sys"
            ]
        )
        if is_it_networking_av or ("electronics & telecommunication" in candidate_full_text and any(w in candidate_full_text for w in ["network", "router", "switch", "support"])):
            return (
                JobTaxonomy.DOMAIN_IT_SOFTWARE,
                [JobTaxonomy.FAMILY_IT_NETWORKING_AV, JobTaxonomy.FAMILY_SOFTWARE_DEV]
            )

        # 3. Plant Electrical Candidate
        is_plant_electrical = any(
            w in candidate_full_text for w in [
                "substation", "transformer", "switchgear", "plant electrical", "ht/lt",
                "electrical maintenance", "high voltage", "power distribution"
            ]
        )
        if is_plant_electrical:
            return (
                JobTaxonomy.DOMAIN_PLANT_OPERATIONS,
                [JobTaxonomy.FAMILY_PLANT_ELECTRICAL, JobTaxonomy.FAMILY_CONTROL_INSTRUMENTATION]
            )

        # 4. Control & Instrumentation Candidate
        if "instrumentation engineer" in candidate_full_text or "plc/scada" in candidate_full_text or "dcs engineer" in candidate_full_text:
            return (
                JobTaxonomy.DOMAIN_PLANT_OPERATIONS,
                [JobTaxonomy.FAMILY_CONTROL_INSTRUMENTATION, JobTaxonomy.FAMILY_PLANT_ELECTRICAL]
            )

        # 5. Quality Control / Laboratory Chemist
        if "qc chemist" in candidate_full_text or "lab analyst" in candidate_full_text or "analytical chemistry" in candidate_full_text:
            return (
                JobTaxonomy.DOMAIN_QUALITY_LAB,
                [JobTaxonomy.FAMILY_QC_LAB, JobTaxonomy.FAMILY_QA_ASSURANCE]
            )

        # 6. Quality Assurance
        if "qa manager" in candidate_full_text or "quality assurance officer" in candidate_full_text:
            return (
                JobTaxonomy.DOMAIN_QUALITY_LAB,
                [JobTaxonomy.FAMILY_QA_ASSURANCE, JobTaxonomy.FAMILY_QC_LAB]
            )

        # 7. EHS & Safety Candidate
        if "safety officer" in candidate_full_text or "ehs engineer" in candidate_full_text or "fire safety" in candidate_full_text:
            return (
                JobTaxonomy.DOMAIN_EHS_ENVIRONMENT,
                [JobTaxonomy.FAMILY_FIRE_SAFETY, JobTaxonomy.FAMILY_ENVIRONMENT_ETP]
            )

        # Default fallback
        return (JobTaxonomy.DOMAIN_OTHER, [JobTaxonomy.FAMILY_OTHER])

    @classmethod
    def are_families_compatible(cls, candidate_families: list[str], job_family: str) -> bool:
        """
        Returns True if candidate_families contains or is compatible with job_family.
        """
        for cand_fam in candidate_families:
            if cand_fam == job_family:
                return True
            compatible_set = JobTaxonomy.COMPATIBILITY_MAP.get(cand_fam, set())
            if job_family in compatible_set:
                return True
        return False
