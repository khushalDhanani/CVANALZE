# backend/tests/test_dynamic_geo_heading_service.py
from app.services.dynamic_geo_heading_service import DynamicGeoAndHeadingService


def test_gazetteer_resolution():
    cities = DynamicGeoAndHeadingService.get_gazetteer_cities()
    assert isinstance(cities, set)
    assert len(cities) > 0
    assert "london" in cities or "new york" in cities

    # Test helper method
    assert DynamicGeoAndHeadingService.is_city_in_gazetteer("New York") is True
    assert DynamicGeoAndHeadingService.is_city_in_gazetteer("London, UK") is True


def test_name_denylist_resolution():
    denylists = DynamicGeoAndHeadingService.get_name_denylist()
    assert isinstance(denylists, set)
    assert len(denylists) > 0
    assert "DEVELOPER" in denylists or "ENGINEER" in denylists

    assert DynamicGeoAndHeadingService.is_word_in_name_denylist("ENGINEER") is True
    assert DynamicGeoAndHeadingService.is_word_in_name_denylist("DEVELOPER") is True


def test_section_headings_resolution():
    headings = DynamicGeoAndHeadingService.get_section_headings()
    assert isinstance(headings, set)
    assert len(headings) > 0
