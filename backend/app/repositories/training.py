import json
from pathlib import Path

from filelock import FileLock

from app.core.config import settings
from app.core.logging import logger
from app.schemas.analysis import TrainingExample


class TrainingRepository:
    @classmethod
    def _get_file_path(cls) -> Path:
        settings.TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)
        return settings.TRAINING_DATA_DIR / "hr_approved.jsonl"

    @classmethod
    def _get_lock_path(cls) -> Path:
        return cls._get_file_path().with_suffix(".lock")

    @classmethod
    def append_training_example(cls, example: TrainingExample) -> None:
        file_path = cls._get_file_path()
        lock_path = cls._get_lock_path()

        with FileLock(lock_path), file_path.open("a", encoding="utf-8") as f:
            f.write(example.model_dump_json() + "\n")

        logger.info(f"Appended training example for scan {example.scan_id}")

    @classmethod
    def load_examples(cls, limit: int = 100) -> list[dict]:
        file_path = cls._get_file_path()
        if not file_path.exists():
            return []

        examples = []
        with file_path.open("r", encoding="utf-8") as f:
            # Read last N lines roughly (or just read all and tail)
            lines = f.readlines()
            for line in lines[-limit:]:
                if line.strip():
                    examples.append(json.loads(line))

        return examples
