# backend/scripts/seed_scoring_profiles_and_stopwords.py
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal, init_db
from app.core.rule_config_manager import RuleConfigManager
from app.models.scoring_profile import ScoringProfileMaster, StopWord

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_scoring_profiles")


def seed_scoring_profiles_and_stopwords():
    logger.info("Initializing DB tables...")
    init_db()

    config = RuleConfigManager.load_config()

    if SessionLocal is None:
        logger.warning("MSSQL SessionLocal is None. Cannot seed MSSQL.")
        return

    db = SessionLocal()
    try:
        # 1. Seed Prefilter Stop Words
        prefilter_cfg = config.scoring.prefilter
        if prefilter_cfg and prefilter_cfg.stop_words:
            logger.info(f"Seeding {len(prefilter_cfg.stop_words)} prefilter stop words...")
            for w in prefilter_cfg.stop_words:
                w_clean = w.strip().lower()
                if w_clean:
                    existing = db.query(StopWord).filter(StopWord.word == w_clean).first()
                    if not existing:
                        db.add(StopWord(word=w_clean, category="prefilter"))
            db.flush()

        # 2. Seed Default Scoring Profile
        lexical_dict = prefilter_cfg.lexical_weights.model_dump() if prefilter_cfg else {}
        match_cfg = config.scoring.match
        penalties_dict = match_cfg.cross_domain_guard.model_dump() if match_cfg else {}
        scoring_params_dict = match_cfg.scoring_parameters.model_dump() if match_cfg else {}

        default_profile = db.query(ScoringProfileMaster).filter(ScoringProfileMaster.profile_code == "DEFAULT").first()
        if not default_profile:
            logger.info("Seeding DEFAULT scoring profile...")
            db.add(
                ScoringProfileMaster(
                    profile_code="DEFAULT",
                    profile_name="Default Enterprise Scoring Profile",
                    description="Default weights, multipliers, penalties, and thresholds.",
                    lexical_weights_json=json.dumps(lexical_dict),
                    penalties_json=json.dumps(penalties_dict),
                    thresholds_json=json.dumps(scoring_params_dict),
                    is_default=True,
                    is_active=True,
                )
            )

        db.commit()
        logger.info("Successfully seeded StopWords and ScoringProfiles into MSSQL!")

    except Exception as exc:
        db.rollback()
        logger.error(f"Error during scoring profile seeding: {exc}", exc_info=True)
    finally:
        db.close()


if __name__ == "__main__":
    seed_scoring_profiles_and_stopwords()
