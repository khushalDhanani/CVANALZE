from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.core.config import settings
from app.services.department_normalizer import DepartmentNormalizer
from app.services.domain_embedding_service import DomainEmbeddingService
from app.services.dynamic_geo_heading_service import DynamicGeoAndHeadingService
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService


def test_dynamic_geo_heading_service_denylists() -> None:
    label_denylist = DynamicGeoAndHeadingService.get_label_prefix_denylist()
    assert isinstance(label_denylist, (set, frozenset))
    assert len(label_denylist) > 0

    non_name_labels = DynamicGeoAndHeadingService.get_non_name_field_labels()
    assert isinstance(non_name_labels, (set, frozenset))
    assert len(non_name_labels) > 0


def test_department_normalizer_refresh_uses_master_data_ttl(monkeypatch) -> None:
    monkeypatch.setattr(settings, "CACHE_TTL_MASTER_DATA_SECONDS", 25)
    original_last_refresh = DepartmentNormalizer._last_refresh
    DepartmentNormalizer._last_refresh = 100.0

    try:
        with (
            patch("time.time", return_value=130.0),
            patch.object(DepartmentNormalizer, "_load_mappings") as load_mappings,
        ):
            DepartmentNormalizer._ensure_cache()
        load_mappings.assert_called_once_with()
    finally:
        DepartmentNormalizer._last_refresh = original_last_refresh


def test_domain_embedding_equivalent_limit_uses_rule_policy() -> None:
    rules = SimpleNamespace(
        canonical_equivalents={
            "skills": {"py": "python", "python3": "python"},
        },
        semantic_equivalence_threshold=0.91,
        max_equivalents=1,
    )

    with (
        patch("app.core.rule_config_manager.RuleConfigManager.get_domain_embedding_rules", return_value=rules),
        patch.object(DomainEmbeddingService, "get_or_generate_domain_embedding", return_value=None),
    ):
        equivalents = DomainEmbeddingService.find_semantic_equivalents(
            "python",
            allow_live_generation=False,
        )

    assert len(equivalents) == 1


def test_degree_pattern_includes_runtime_configured_degrees() -> None:
    education_field = SimpleNamespace(
        get_keyword_set=lambda category: {"Licentiate"} if category == "degrees" else set(),
    )
    config = SimpleNamespace(fields={"education": education_field})

    with (
        patch("app.services.dynamic_geo_heading_service.PostgresAppSession", None),
        patch("app.services.dynamic_geo_heading_service.RuleConfigManager.load_config", return_value=config),
    ):
        DynamicGeoAndHeadingService.refresh_cache()
        pattern = DynamicGeoAndHeadingService.get_degree_pattern()

    assert pattern.search("Licentiate in Applied Science") is not None


def test_dynamic_taxonomy_service_add_designation_input_validation() -> None:
    # Empty designation name should return False
    assert DynamicTaxonomyService.add_designation("", "Software Engineering") is False
    # Empty family name should return False
    assert DynamicTaxonomyService.add_designation("Python Developer", "") is False
