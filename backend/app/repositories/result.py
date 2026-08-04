import json
from pathlib import Path
from typing import Any

from app.core.cache import _REDIS_CLIENT, CacheIndex, cv_result_cache_manager
from app.core.config import settings
from app.core.cv_identity import CVIdentity, CVIdentityCollisionError
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
        for legacy_key in data.get("legacy_cv_keys") or []:
            CacheIndex.add("cv_legacy_alias", str(legacy_key).lower(), filename)

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
    def assert_identity_available(
        cls,
        identity: CVIdentity,
        content_hash: str,
        *,
        allow_legacy_content_change: bool = False,
    ) -> None:
        existing = cls.read_result_by_filename(f"{identity.canonical_key}.json")
        if existing is None:
            return

        existing_candidate_id = cls._optional_str(existing.get("candidate_id"))
        existing_cv_id = cls._optional_str(existing.get("cv_id"))
        if identity.uses_supplied_ids:
            if existing_candidate_id == identity.candidate_id and existing_cv_id == identity.cv_id:
                return
        elif existing_candidate_id is None and existing_cv_id is None:
            if existing.get("cv_hash") == content_hash or allow_legacy_content_change:
                return

        raise CVIdentityCollisionError(f"CV identity collision for '{identity.canonical_key}'. Supply distinct candidate_id/cv_id values or reprocess the existing record.")

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

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

        # 3. Fallback search by exact stored scan ID.
        matches = cls.find_results_by_scan_id(stem)
        if matches:
            for match in matches:
                try:
                    alt_res = cls.read_result(match)
                    if alt_res and alt_res.get("status") not in ("processing", None):
                        return alt_res
                except Exception as exc:
                    logger.warning(f"Failed loading matched result for stem {stem}: {exc}")

        # 4. Legacy filename aliases resolve only when unambiguous.
        alias_matches = cls._find_results_by_legacy_alias(stem)
        if len(alias_matches) == 1:
            return alias_matches[0]
        if len(alias_matches) > 1:
            logger.warning(f"Legacy CV key '{stem}' is ambiguous across {len(alias_matches)} canonical identities.")
            return None

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
                    for key in keys:
                        redis_path = f"redis://{key}"
                        try:
                            data = cls.read_result(redis_path)
                            if cls._result_matches_scan_id(data, scan_id):
                                results.append(redis_path)
                        except Exception:
                            continue
                    if cursor == 0:
                        break
            except Exception as exc:
                logger.warning(f"Redis scan failed for scan_id {scan_id}: {exc}")

        if settings.RESULTS_DIR.exists():
            for path in sorted(settings.RESULTS_DIR.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if cls._result_matches_scan_id(data, scan_id):
                        results.append(path)
                except Exception:
                    continue

        return results

    @classmethod
    def _find_results_by_legacy_alias(cls, cv_key: str) -> list[dict[str, Any]]:
        normalized_key = cv_key.removesuffix(".json").lower()
        candidate_filenames = CacheIndex.get_keys("cv_legacy_alias", normalized_key)
        matches: dict[str, dict[str, Any]] = {}

        for filename in candidate_filenames:
            data = cls.read_result_by_filename(filename)
            if data and normalized_key in {str(key).lower() for key in data.get("legacy_cv_keys") or []}:
                matches[str(data.get("id") or filename)] = data

        for data in cls.list_all_results():
            aliases = {str(key).lower() for key in data.get("legacy_cv_keys") or []}
            if normalized_key in aliases:
                matches[str(data.get("id") or data.get("scan_id") or id(data))] = data

        return list(matches.values())

    @staticmethod
    def _result_matches_scan_id(data: dict[str, Any], scan_id: str) -> bool:
        target = scan_id.removesuffix(".json").lower()
        target_without_prefix = target.removeprefix("cv_")
        for value in (data.get("id"), data.get("scan_id")):
            if value is None:
                continue
            normalized = str(value).removesuffix(".json").lower()
            if normalized == target or normalized.removeprefix("cv_") == target_without_prefix:
                return True
        return False

    @classmethod
    def list_all_results(cls) -> list[dict[str, Any]]:
        results_by_id: dict[str, dict[str, Any]] = {}

        # 1. Read from Redis if available
        if _REDIS_CLIENT:
            try:
                cursor = 0
                pattern = "cv_result:*.json"
                while True:
                    cursor, keys = _REDIS_CLIENT.scan(cursor=cursor, match=pattern, count=100)
                    for key in keys:
                        try:
                            val = _REDIS_CLIENT.get(key)
                            if val:
                                data = json.loads(val)
                                if isinstance(data, dict):
                                    item_id = str(data.get("id") or data.get("scan_id") or key).lower()
                                    results_by_id[item_id] = data
                        except Exception:
                            continue
                    if cursor == 0:
                        break
            except Exception as exc:
                logger.warning(f"Redis scan failed in list_all_results: {exc}")

        # 2. Read from disk files
        if settings.RESULTS_DIR.exists():
            for p in sorted(settings.RESULTS_DIR.glob("*.json"), reverse=True):
                if p.name.endswith(".tmp"):
                    continue
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        item_id = str(data.get("id") or data.get("scan_id") or p.stem).lower()
                        # Disk content merges and updates candidate entry
                        if item_id not in results_by_id or (data.get("parsed_at") or "") >= (results_by_id[item_id].get("parsed_at") or ""):
                            results_by_id[item_id] = data
                except Exception:
                    pass

        items = list(results_by_id.values())
        items.sort(key=lambda x: str(x.get("created_at") or x.get("parsed_at") or ""), reverse=True)
        return items
