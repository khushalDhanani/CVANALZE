import json
from pathlib import Path
from typing import Any

from app.core.cache import _REDIS_CLIENT, cv_result_cache_manager
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
    def resolve_result(cls, cv_key: str) -> dict[str, Any] | None:
        """
        Idempotently resolves result dictionary by cv_key, handling prefix variations (cv_ / CV_),
        stem searching, and fallback disk lookups. Prefers completed results over interim processing markers.
        """
        clean_key = cv_key.strip()
        filename = f"{clean_key}.json" if not clean_key.endswith(".json") else clean_key
        stem = filename.removesuffix(".json")

        # 1. Direct filename read
        direct_res = cls.read_result_by_filename(filename)
        if direct_res and direct_res.get("status") not in ("processing", None):
            return direct_res

        # 2. Case variation & prefix normalization check
        stems_to_try = [stem]
        if stem.lower().startswith("cv_"):
            stems_to_try.append(stem[3:])
            stems_to_try.append(f"cv_{stem[3:]}")
            stems_to_try.append(f"CV_{stem[3:]}")
        else:
            stems_to_try.append(f"cv_{stem}")

        for s in stems_to_try:
            fn = f"{s}.json"
            alt_res = cls.read_result_by_filename(fn)
            if alt_res and alt_res.get("status") not in ("processing", None):
                return alt_res

        # 3. Fallback search by scan_id / glob
        matches = cls.find_results_by_scan_id(stem)
        if matches:
            for match in matches:
                try:
                    alt_res = cls.read_result(match)
                    if alt_res and alt_res.get("status") not in ("processing", None):
                        return alt_res
                except Exception as exc:
                    logger.warning(f"Failed loading matched result for stem {stem}: {exc}")

        # Return direct_res (even if processing) if no completed result was found anywhere
        if direct_res:
            return direct_res

        return None

    @classmethod
    def exists(cls, filename: str) -> bool:
        return cv_result_cache_manager.exists(filename) or (settings.RESULTS_DIR / filename).is_file()

    @classmethod
    def find_results_by_scan_id(cls, scan_id: str) -> list[str | Path]:
        results: list[str | Path] = []
        if _REDIS_CLIENT:
            try:
                cursor = 0
                pattern = f"cv_result:*{scan_id}*.json"
                while True:
                    cursor, keys = _REDIS_CLIENT.scan(cursor=cursor, match=pattern, count=100)
                    results.extend([f"redis://{k}" for k in keys])
                    if cursor == 0:
                        break
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
