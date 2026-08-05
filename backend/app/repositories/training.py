import json
from app.core.database import SessionLocal
from app.core.logging import logger
from app.models.training import HRFeedback
from app.schemas.analysis import TrainingExample


class TrainingRepository:
    @classmethod
    def append_training_example(cls, example: TrainingExample) -> None:
        try:
            with SessionLocal() as db:
                feedback = HRFeedback(
                    scan_id=example.scan_id,
                    candidate_id=example.candidate_id,
                    vacancy_id=example.vacancy_id,
                    feedback_payload_json=example.model_dump_json()
                )
                db.add(feedback)
                db.commit()
                logger.info(f"Appended training example for scan {example.scan_id} into database")
        except Exception as e:
            logger.error(f"Failed to append training example to DB: {e}")

    @classmethod
    def load_examples(cls, limit: int = 100) -> list[dict]:
        try:
            with SessionLocal() as db:
                rows = db.query(HRFeedback).order_by(HRFeedback.created_at.desc()).limit(limit).all()
                examples = []
                for row in reversed(rows):  # Return chronological if desired
                    examples.append(json.loads(row.feedback_payload_json))
                return examples
        except Exception as e:
            logger.error(f"Failed to load training examples from DB: {e}")
            return []
