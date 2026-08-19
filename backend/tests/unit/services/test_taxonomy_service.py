from __future__ import annotations

from app.services.dynamic_geo_heading_service import DynamicGeoAndHeadingService
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService


def test_dynamic_geo_heading_service_denylists() -> None:
    label_denylist = DynamicGeoAndHeadingService.get_label_prefix_denylist()
    assert isinstance(label_denylist, (set, frozenset))
    assert len(label_denylist) > 0

    non_name_labels = DynamicGeoAndHeadingService.get_non_name_field_labels()
    assert isinstance(non_name_labels, (set, frozenset))
    assert len(non_name_labels) > 0


def test_dynamic_taxonomy_service_add_designation_input_validation() -> None:
    # Empty designation name should return False
    assert DynamicTaxonomyService.add_designation("", "Software Engineering") is False
    # Empty family name should return False
    assert DynamicTaxonomyService.add_designation("Python Developer", "") is False
