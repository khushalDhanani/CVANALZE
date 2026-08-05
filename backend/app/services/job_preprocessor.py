# backend/app/services/job_preprocessor.py
import re
from typing import Any

from app.services.department_normalizer import DepartmentNormalizer
from app.services.job_taxonomy import TaxonomyClassifier


class JobPreprocessor:
    """
    Dedicated service for pre-processing raw job dictionaries.
    Populates taxonomy classification metadata, title terms, department terms,
    normalized skill sets, and industry-normalized labels once during data ingestion/caching.
    """

    @classmethod
    def preprocess_job(cls, job: dict[str, Any]) -> dict[str, Any]:
        """Precomputes and caches tokens, taxonomy metadata, and industry labels on a job dictionary."""
        stop_words = {
            "and",
            "team",
            "for",
            "the",
            "with",
            "senior",
            "junior",
            "lead",
            "manager",
            "specialist",
        }

        # 1. Precompute Department Name
        dept_name = (job.get("department_name") or job.get("department") or "").lower()
        job["_precomputed_dept"] = dept_name

        # 2. Precompute Title Terms
        title = job.get("title", "").lower()
        title_terms = [t for t in re.split(r"[\s/&()\-,]+", title) if len(t) > 2 and t not in stop_words]
        job["_precomputed_title_terms"] = title_terms

        # 3. Precompute Required Skills
        req_skills = job.get("required_skills", [])
        job["_precomputed_req_skills"] = [s.lower() for s in req_skills if isinstance(s, str)]

        # 4. Precompute Preferred Keywords
        pref_keywords = job.get("preferred_keywords", [])
        job["_precomputed_pref_keywords"] = [k.lower() for k in pref_keywords if isinstance(k, str)]

        # 5. Populate Taxonomy Metadata
        domain, job_family = TaxonomyClassifier.classify_vacancy(job)
        job["domain"] = domain
        job["job_family"] = job_family
        job["_precomputed_domain"] = domain
        job["_precomputed_job_family"] = job_family

        # 6. Populate Industry-Normalized Labels (from DepartmentNormalizer)
        raw_dept = job.get("department_name") or job.get("department") or ""
        raw_title = job.get("title") or ""
        dept_norm = DepartmentNormalizer.normalize_department(raw_dept)
        title_norm = DepartmentNormalizer.normalize_designation(raw_title)
        job["_precomputed_industry_dept"] = dept_norm.get("industry_department")
        job["_precomputed_industry_title"] = title_norm.get("industry_designation")

        return job

    @classmethod
    def preprocess_job_dicts(cls, job_dicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Precomputes fields for a list of job dictionaries."""
        return [cls.preprocess_job(j) for j in job_dicts]
