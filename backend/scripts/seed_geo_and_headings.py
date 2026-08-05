# backend/scripts/seed_geo_and_headings.py
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import PostgresAppSession, init_db
from app.core.rule_config_manager import RuleConfigManager
from app.models.geo_headings import GeoLocation, NameDenylist, SectionHeading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_geo_headings")


def seed_geo_and_headings():
    logger.info("Initializing DB tables...")
    init_db()

    config = RuleConfigManager.load_config()

    if PostgresAppSession is None:
        logger.warning("PostgresAppSession is None. Cannot seed database.")
        return

    db = PostgresAppSession()
    try:
        # 1. Seed Geo Locations (Gazetteer)
        gazetteer = config.fields.get("location", None)
        if gazetteer and gazetteer.keywords.get("gazetteer"):
            cities = gazetteer.keywords["gazetteer"]
            logger.info(f"Seeding {len(cities)} location gazetteer entries...")
            for city in cities:
                city_clean = city.strip().title()
                if city_clean:
                    existing = db.query(GeoLocation).filter(GeoLocation.city_name == city_clean).first()
                    if not existing:
                        db.add(GeoLocation(city_name=city_clean, country_name="Global"))
            db.flush()

        # 2. Seed Name Denylists (Job Title & Header Denylists)
        name_cfg = config.fields.get("name", None)
        if name_cfg:
            job_titles = name_cfg.keywords.get("job_title_denylist", [])
            logger.info(f"Seeding {len(job_titles)} job title denylist entries...")
            for word in job_titles:
                word_clean = word.strip().upper()
                if word_clean:
                    existing = db.query(NameDenylist).filter(NameDenylist.word == word_clean).first()
                    if not existing:
                        db.add(NameDenylist(word=word_clean, category="job_title"))

            headers = name_cfg.keywords.get("header_denylist", [])
            logger.info(f"Seeding {len(headers)} header denylist entries...")
            for word in headers:
                word_clean = word.strip().upper()
                if word_clean:
                    existing = db.query(NameDenylist).filter(NameDenylist.word == word_clean).first()
                    if not existing:
                        db.add(NameDenylist(word=word_clean, category="header"))
            db.flush()

        # 3. Seed Generic Section Headings
        company_cfg = config.fields.get("company_name", None)
        if company_cfg:
            generic_headers = company_cfg.keywords.get("generic_section_headers", [])
            logger.info(f"Seeding {len(generic_headers)} section heading entries...")
            for head in generic_headers:
                head_clean = head.strip().lower()
                if head_clean:
                    existing = db.query(SectionHeading).filter(SectionHeading.heading_text == head_clean).first()
                    if not existing:
                        db.add(SectionHeading(heading_text=head_clean, category="generic"))

        db.commit()
        logger.info("Successfully seeded GeoLocations, SectionHeadings, and NameDenylists into MSSQL!")

    except Exception as exc:
        db.rollback()
        logger.error(f"Error during geo/heading seeding: {exc}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    seed_geo_and_headings()
