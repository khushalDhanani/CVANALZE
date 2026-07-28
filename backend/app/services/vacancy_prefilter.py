import re
from typing import Any

from app.core.config import settings
from app.core.logging import logger


class VacancyPreFilter:
    """
    Lightweight deterministic Python pre-filter to narrow down active database vacancies
    to the top relevant candidates before passing them to the LLM.
    """

    @classmethod
    def filter_vacancies(
        cls,
        cv_text: str,
        openings: list[dict[str, Any]],
        candidate_experience: float | None = None,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        if not openings:
            return []

        limit = top_k or settings.PREFILTER_TOP_K
        if len(openings) <= limit:
            return openings

        cv_lower = cv_text.lower()
        scored_vacancies: list[tuple[float, dict[str, Any]]] = []

        stop_words = {"and", "team", "for", "the", "with", "senior", "junior", "lead", "manager", "developer", "engineer", "specialist"}

        for job in openings:
            score = 0.0

            # 1. Department match
            dept_name = job.get("_precomputed_dept")
            if dept_name is None:
                dept_name = (job.get("department_name") or job.get("department") or "").lower()
            if dept_name and dept_name in cv_lower:
                score += 30.0

            # 2. Title term match
            title_terms = job.get("_precomputed_title_terms")
            if title_terms is None:
                title = job.get("title", "").lower()
                title_terms = [
                    t for t in re.split(r"[\s/&()\-,]+", title)
                    if len(t) > 2 and t not in stop_words
                ]
            title_matches = [t for t in title_terms if t in cv_lower]
            score += len(title_matches) * 15.0

            # 3. Required skills match
            req_skills = job.get("_precomputed_req_skills")
            if req_skills is None:
                req_skills = [s.lower() for s in job.get("required_skills", []) if isinstance(s, str)]
            for skill in req_skills:
                if skill in cv_lower:
                    score += 10.0

            # 4. Preferred keywords match
            pref_keywords = job.get("_precomputed_pref_keywords")
            if pref_keywords is None:
                pref_keywords = [k.lower() for k in job.get("preferred_keywords", []) if isinstance(k, str)]
            for kw in pref_keywords:
                if kw in cv_lower:
                    score += 5.0

            # 5. Experience suitability
            min_exp = job.get("min_experience_years")
            max_exp = job.get("max_experience_years")
            if candidate_experience is not None:
                if (min_exp is None or candidate_experience >= min_exp) and (max_exp is None or candidate_experience <= max_exp):
                    score += 10.0

            # Attach temporary score for ranking
            job_copy = dict(job)
            job_copy["_prefilter_score"] = score
            scored_vacancies.append((score, job_copy))

        # Sort descending by score
        scored_vacancies.sort(key=lambda item: item[0], reverse=True)

        # Extract top K
        selected = [item[1] for item in scored_vacancies[:limit]]

        logger.info(
            f"Vacancy Pre-filter: {len(openings)} total vacancies reduced to {len(selected)} candidate vacancies (Top K={limit})."
        )
        return selected
