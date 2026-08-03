# backend/app/services/dynamic_geo_heading_service.py
import logging

from app.core.database import SessionLocal
from app.core.rule_config_manager import RuleConfigManager
from app.models.geo_headings import GeoLocation, NameDenylist, SectionHeading

logger = logging.getLogger("cv_analyzer")


class DynamicGeoAndHeadingService:
    """
    Dynamic Location Gazetteer, Section Heading, and Name Denylist Service.
    Queries MSSQL cvai schema with in-memory set caching and fallback to RuleConfigManager.
    """

    _gazetteer_cache: set[str] | None = None
    _name_denylist_cache: set[str] | None = None
    _section_heading_cache: set[str] | None = None

    @classmethod
    def get_gazetteer_cities(cls) -> set[str]:
        if cls._gazetteer_cache is None:
            cls.refresh_cache()
        return cls._gazetteer_cache or set()

    @classmethod
    def get_name_denylist(cls) -> set[str]:
        if cls._name_denylist_cache is None:
            cls.refresh_cache()
        return cls._name_denylist_cache or set()

    @classmethod
    def get_section_headings(cls) -> set[str]:
        if cls._section_heading_cache is None:
            cls.refresh_cache()
        return cls._section_heading_cache or set()

    @classmethod
    def refresh_cache(cls) -> None:
        cities: set[str] = set()
        denylists: set[str] = set()
        headings: set[str] = set()

        # 1. Load from MSSQL if available
        if SessionLocal is not None:
            try:
                with SessionLocal() as session:
                    db_cities = session.query(GeoLocation.city_name).filter(GeoLocation.is_active == True).all()
                    cities.update(c[0].strip().lower() for c in db_cities if c[0])

                    db_denylists = session.query(NameDenylist.word).filter(NameDenylist.is_active == True).all()
                    denylists.update(d[0].strip().upper() for d in db_denylists if d[0])

                    db_headings = session.query(SectionHeading.heading_text).filter(SectionHeading.is_active == True).all()
                    headings.update(h[0].strip().lower() for h in db_headings if h[0])
            except Exception as exc:
                logger.warning(f"[DYNAMIC_GEO_HEADING] MSSQL query failed: {exc}")

        # 2. Fallback / merge from rule_config.json
        try:
            config = RuleConfigManager.load_config()
            loc_field = config.fields.get("location")
            if loc_field:
                cities.update(loc_field.get_keyword_set("gazetteer"))

            name_field = config.fields.get("name")
            if name_field:
                denylists.update(name_field.get_upper_keyword_set("job_title_denylist"))
                denylists.update(name_field.get_upper_keyword_set("header_denylist"))

            comp_field = config.fields.get("company_name")
            if comp_field:
                headings.update(comp_field.get_keyword_set("generic_section_headers"))
        except Exception as exc:
            logger.warning(f"[DYNAMIC_GEO_HEADING] Config fallback failed: {exc}")

        cls._gazetteer_cache = cities
        cls._name_denylist_cache = denylists
        cls._section_heading_cache = headings
        logger.info(f"[DYNAMIC_GEO_HEADING] Cache refreshed: {len(cities)} gazetteer cities, {len(denylists)} name denylists, {len(headings)} section headings.")

    @classmethod
    def is_city_in_gazetteer(cls, city_or_location: str) -> bool:
        clean = city_or_location.strip().lower()
        if not clean:
            return False
        gazetteer = cls.get_gazetteer_cities()
        return clean in gazetteer or any(city in clean for city in gazetteer if len(city) > 3)

    @classmethod
    def is_word_in_name_denylist(cls, word: str) -> bool:
        clean = word.strip().upper()
        if not clean:
            return False
        return clean in cls.get_name_denylist()
