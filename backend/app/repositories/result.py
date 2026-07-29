import json
import os
from pathlib import Path
from typing import Any

from app.core.cache import cv_result_cache_manager, _REDIS_CLIENT
from app.core.config import settings
from app.core.logging import logger


class ResultRepository:
    """
    Repository for storing and retrieving CV analysis result JSON files.
    Delegates primary storage to CacheManager (Redis L2 + File L3) while
    preserving the redis:// URI return convention for backward compatibility.
    """

    CACHE_TTL_SECONDS = 604800

    @classmethod
    def save_result(cls, filename: str, data: dict[str, Any]) -> Path:
        return cls.atomic_save_result(filename, data)

    @classmethod
    def atomic_save_result(cls, filename: str, data: dict[str, Any]) -> Path | str:
        cv_result_cache_manager.set(filename, data, ttl=cls.CACHE_TTL_SECONDS)

        settings.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        result_path = (settings.RESULTS_DIR / filename).resolve()

        if not result_path.is_relative_to(settings.RESULTS_DIR.resolve()):
            raise ValueError(f"Invalid filename prevents saving outside results directory: {filename}")

        tmp_path = result_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(result_path)

        logger.info(f"Atomically saved result to disk '{result_path}'.")

        if _REDIS_CLIENT:
            redis_key = f"cv_result:{filename}"
            logger.info(f"Saved result to Redis '{redis_key}'.")
            return f"redis://{redis_key}"

        return result_path

    @classmethod
    def read_result(cls, filepath: str | Path) -> dict[str, Any]:
        if isinstance(filepath, str) and filepath.startswith("redis://"):
            if not _REDIS_CLIENT:
                raise RuntimeError("Redis client is not configured but a redis path was requested.")
            redis_key = filepath[8:]
            val = _REDIS_CLIENT.get(redis_key)
            if not val:
                raise FileNotFoundError(f"Result not found in Redis: {redis_key}")
            return json.loads(val)

        path = Path(filepath).resolve()
        if not path.is_relative_to(settings.RESULTS_DIR.resolve()):
            raise ValueError(f"Invalid filepath attempts to read outside results directory: {filepath}")

        if not path.exists():
            raise FileNotFoundError(f"Result file not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def read_result_by_filename(cls, filename: str) -> dict[str, Any] | None:
        result = cv_result_cache_manager.get(filename)
        if result is not None:
            return result
        path = settings.RESULTS_DIR / filename
        if path.exists() and path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                cv_result_cache_manager.set(filename, data, ttl=cls.CACHE_TTL_SECONDS)
                return data
            except Exception as exc:
                logger.warning(f"Failed reading result file {path}: {exc}")
        return None

    @classmethod
    def exists(cls, filename: str) -> bool:
        return cv_result_cache_manager.exists(filename) or (settings.RESULTS_DIR / filename).is_file()

    @classmethod
    def find_results_by_scan_id(cls, scan_id: str) -> list[str | Path]:
        results: list[str | Path] = []
        if _REDIS_CLIENT:
            try:
                keys = _REDIS_CLIENT.keys(f"cv_result:*{scan_id}*.json")
                results.extend([f"redis://{k}" for k in keys])
            except Exception as exc:
                logger.warning(f"Redis scan failed for scan_id {scan_id}: {exc}")

        if settings.RESULTS_DIR.exists():
            results.extend(sorted(settings.RESULTS_DIR.glob(f"*{scan_id}*.json")))

        return results

    @classmethod
    def list_all_results(cls) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if settings.RESULTS_DIR.exists():
            for p in sorted(settings.RESULTS_DIR.glob("*.json"), reverse=True):
                if p.name.endswith(".tmp"):
                    continue
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    items.append(data)
                except Exception:
                    pass
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return items
