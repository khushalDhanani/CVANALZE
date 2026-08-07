import pytest
from app.services.date_interval_parser import DateIntervalParser


def test_spanish_french_german_dates():
    # Spanish: Enero 2019 - Diciembre 2021
    interval_es = DateIntervalParser.parse_interval("Enero 2019 - Diciembre 2021")
    assert interval_es.start_date == "2019-01-01"
    assert interval_es.end_date == "2021-12-31"
    assert interval_es.confidence >= 0.9

    # French: Janvier 2020 - Présent
    interval_fr = DateIntervalParser.parse_interval("Janvier 2020 - Present")
    assert interval_fr.start_date == "2020-01-01"
    assert interval_fr.is_current is True

    # German: Januar 2018 bis Dezember 2020
    interval_de = DateIntervalParser.parse_interval("Januar 2018 bis Dezember 2020")
    assert interval_de.start_date == "2018-01-01"
    assert interval_de.end_date == "2020-12-31"


def test_seasons_and_quarters():
    # Summer 2020 - Fall 2022
    interval_season = DateIntervalParser.parse_interval("Summer 2020 - Fall 2022")
    assert interval_season.start_date is not None
    assert interval_season.end_date is not None
    assert interval_season.duration_months >= 24

    # Q1 2019 to Q4 2021
    interval_q = DateIntervalParser.parse_interval("Q1 2019 to Q4 2021")
    assert interval_q.start_date == "2019-01-01"
    assert interval_q.end_date == "2021-12-31"


def test_fuzzy_and_partial_date_ranges():
    # Partial short year: 2018-21
    interval_short = DateIntervalParser.parse_interval("2018-21")
    assert interval_short.start_date == "2018-01-01"
    assert interval_short.end_date == "2021-12-31"

    # Parenthetical dates: (03/2019 ~ 08/2022)
    interval_paren = DateIntervalParser.parse_interval("(03/2019 ~ 08/2022)")
    assert interval_paren.start_date == "2019-03-01"
    assert interval_paren.end_date == "2022-08-31"

    # Present synonym: 2020 to Till Date
    interval_present = DateIntervalParser.parse_interval("2020 to Till Date")
    assert interval_present.start_date == "2020-01-01"
    assert interval_present.is_current is True


def test_bare_code_token_not_parsed_as_date():
    """A non-date token like 'RAID-5' must NOT fabricate a Jan-2000 interval."""
    interval = DateIntervalParser.parse_interval("RAID-5")
    assert interval.start_date is None
    assert interval.end_date is None
    assert interval.duration_months is None
    assert interval.confidence == 0.0
