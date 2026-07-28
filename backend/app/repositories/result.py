import json
import os
from pathlib import Path
from typing import Any

import redis

from app.core.config import settings
from app.core.logging import logger

_redis_client = None
if settings.REDIS_URL:
    try:
        _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        _redis_client.ping()
        logger.info(f"Connected to Redis cache at {settings.REDIS_URL}")
    except Exception as exc:
        logger.warning(f"Failed to connect to Redis, falling back to disk cache: {exc}")
        _redis_client = None


class ResultRepository:
    """
    Repository for storing and retrieving CV analysis result JSON files.
    """

    @classmethod
    def save_result(cls, filename: str, data: dict[str, Any]) -> Path:
        return cls.atomic_save_result(filename, data)

    @classmethod
    def atomic_save_result(cls, filename: str, data: dict[str, Any]) -> Path | str:
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        
        if _redis_client:
            redis_key = f"cv_result:{filename}"
            _redis_client.set(redis_key, payload)
            _redis_client.expire(redis_key, 604800)  # 7 days expiration
            logger.info(f"Saved result to Redis '{redis_key}'.")
            return f"redis://{redis_key}"

        settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        result_path = (settings.RESULTS_DIR / filename).resolve()
        
        if not result_path.is_relative_to(settings.RESULTS_DIR.resolve()):
            raise ValueError(f"Invalid filename prevents saving outside results directory: {filename}")
            
        tmp_path = settings.RESULTS_DIR / f"{filename}.tmp"

        tmp_path.write_text(payload, encoding="utf-8")
        os.replace(tmp_path, result_path)

        logger.info(f"Atomically saved result to '{result_path}'.")
        return result_path

    @classmethod
    def read_result(cls, filepath: str | Path) -> dict[str, Any]:
        if isinstance(filepath, str) and filepath.startswith("redis://"):
            if not _redis_client:
                raise RuntimeError("Redis client is not configured but a redis path was requested.")
            redis_key = filepath[8:]
            payload = _redis_client.get(redis_key)
            if not payload:
                raise FileNotFoundError(f"Result not found in Redis: {redis_key}")
            return json.loads(payload)

        path = Path(filepath).resolve()
        if not path.is_relative_to(settings.RESULTS_DIR.resolve()):
            raise ValueError(f"Invalid filepath attempts to read outside results directory: {filepath}")
            
        if not path.exists():
            raise FileNotFoundError(f"Result file not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def read_result_by_filename(cls, filename: str) -> dict[str, Any] | None:
        if _redis_client:
            redis_key = f"cv_result:{filename}"
            try:
                payload = _redis_client.get(redis_key)
                if payload:
                    return json.loads(payload)
            except Exception as exc:
                logger.exception(f"Failed to read result from Redis '{redis_key}': {exc}")
                return None

        result_path = (settings.RESULTS_DIR / filename).resolve()
        if not result_path.is_relative_to(settings.RESULTS_DIR.resolve()):
            logger.warning(f"Path traversal attempt blocked for reading: {filename}")
            return None
            
        if not result_path.exists():
            return None
        try:
            return json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"Failed to read result file '{result_path}': {exc}")
            return None

    @classmethod
    def exists(cls, filename: str) -> bool:
        return (settings.RESULTS_DIR / filename).is_file()

    @classmethod
    def find_results_by_scan_id(cls, scan_id: str) -> list[str | Path]:
        results = []
        if _redis_client:
            keys = _redis_client.keys(f"cv_result:*{scan_id}*.json")
            results.extend([f"redis://{k}" for k in keys])
            
        if settings.RESULTS_DIR.exists():
            results.extend(list(settings.RESULTS_DIR.glob(f"*{scan_id}*.json")))
            
        return results

