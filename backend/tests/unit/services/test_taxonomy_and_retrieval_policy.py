from __future__ import annotations

from unittest.mock import patch

from app.core.rule_config_manager import PolicyRegistry, TaxonomyPolicy
from app.schemas.classification_types import TaxonomyRelationType
from app.schemas.job_context import JobEvaluationContext
from app.services.job_taxonomy import TaxonomyClassifier
from app.services.vacancy_prefilter import VacancyPreFilter


def test_taxonomy_relation_type_and_policy_scores() -> None:
    """Workstream 4.3: TaxonomyRelationType values and TaxonomyPolicy relation_scores."""
    snapshot = PolicyRegistry.resolve_snapshot()
    taxonomy_policy = snapshot.taxonomy

    assert isinstance(taxonomy_policy, TaxonomyPolicy)
    assert taxonomy_policy.relation_scores["EXACT"] == 1.0
    assert taxonomy_policy.relation_scores["ALLOWED"] == 0.85
    assert taxonomy_policy.relation_scores["RELATED"] == 0.50
    assert taxonomy_policy.relation_scores["DISALLOWED"] == 0.0

    assert TaxonomyRelationType.EXACT.value == "EXACT"
    assert TaxonomyRelationType.ALLOWED.value == "ALLOWED"
    assert TaxonomyRelationType.RELATED.value == "RELATED"
    assert TaxonomyRelationType.DISALLOWED.value == "DISALLOWED"


def test_job_taxonomy_family_compatibility_uses_policy_min_score() -> None:
    """Workstream 4.3: Are families compatible uses PolicySnapshot min score."""
    snapshot = PolicyRegistry.resolve_snapshot()
    min_score = snapshot.taxonomy.family_compatibility_min_score

    assert min_score == 0.40
    # Exact family match always returns True
    assert TaxonomyClassifier.are_families_compatible(["Software Engineering"], "Software Engineering") is True


def test_small_candidate_set_prefilter_bypassed_flag() -> None:
    """Workstream 4.3: Small candidate set (<= limit) is marked BYPASSED_SMALL_SET with no score fabrication."""
    cv_text = """
    Jane Doe
    Python Developer
    Email: jane@example.com
    
    ## SKILLS
    Python, FastAPI
    """

    job_dict = {
        "id": "vac-small-1",
        "vacancy_id": 1,
        "title": "Python Engineer",
        "department": "Engineering",
        "required_skills": ["Python"],
    }
    job_ctx = JobEvaluationContext.create(job_dict)

    mock_emb = [0.05] * 768
    with patch("app.services.embedding_service.EmbeddingService.generate_embedding", return_value=mock_emb):
        res = VacancyPreFilter.filter_vacancies(
            cv_text=cv_text,
            openings=[job_ctx],
            top_k=10,
        )

    assert len(res) == 1
    raw_job = res[0]
    assert raw_job.get("_prefilter_score") is None
    rrf = raw_job.get("_rrf_details", {})
    assert rrf.get("rrf_score") is None
    assert rrf.get("retrieval_path") == "BYPASSED_SMALL_SET"
    assert rrf.get("quality_flag") == "BYPASSED_SMALL_SET"
