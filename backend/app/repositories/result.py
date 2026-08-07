from __future__ import annotations
import json
from pathlib import Path
from typing import Any


from app.core.cache import _REDIS_CLIENT, CacheIndex, cv_result_cache_manager
from app.core.cv_identity import CVIdentity, CVIdentityCollisionError
from app.core.database import PostgresAppSession
from app.core.logging import logger
from app.models.result import CVResult


class ResultRepository:
    """
    Repository for storing and retrieving CV analysis results.
    Delegates primary storage to PostgreSQL (CVResult table) and CacheManager (Redis L2) 
    while preserving backward compatibility for JSON cache retrieval.
    """

    CACHE_TTL_SECONDS = 604800

    @classmethod
    def save_result(cls, filename: str, data: dict[str, Any]) -> str:
        return cls.atomic_save_result(filename, data)

    @classmethod
    def atomic_save_result(cls, filename: str, data: dict[str, Any]) -> str:
        cv_result_cache_manager.set(filename, data, ttl=cls.CACHE_TTL_SECONDS)
        for legacy_key in data.get("legacy_cv_keys") or []:
            CacheIndex.add("cv_legacy_alias", str(legacy_key).lower(), filename)

        cv_key = filename.removesuffix(".json")
        status = data.get("status")
        full_name = data.get("candidate_name") or data.get("full_name")
        candidate_id = cls._optional_str(data.get("candidate_id"))
        cv_id = cls._optional_str(data.get("cv_id"))
        cv_hash = cls._optional_str(data.get("cv_hash"))
        
        resume_json = data.get("resume_json")
        match_analysis = data.get("match_analysis")
        text_content = data.get("text")
        markdown_content = data.get("markdown")

        try:
            with PostgresAppSession() as session:
                result_obj = session.query(CVResult).filter(CVResult.cv_key == cv_key).first()
                if not result_obj:
                    result_obj = CVResult(cv_key=cv_key)
                    session.add(result_obj)
                
                result_obj.status = status
                result_obj.full_name = full_name
                result_obj.candidate_id = candidate_id
                result_obj.cv_id = cv_id
                result_obj.cv_hash = cv_hash
                result_obj.resume_json = resume_json
                result_obj.match_analysis = match_analysis
                result_obj.text_content = text_content
                result_obj.markdown_content = markdown_content
                result_obj.raw_data = data
                
                session.commit()
                logger.info(f"Atomically saved result to PostgreSQL 'cv_results' for cv_key '{cv_key}'.")
        except Exception as exc:
            logger.error(f"Failed to save CV result {cv_key} to PostgreSQL: {exc}")

        if _REDIS_CLIENT:
            redis_key = f"cv_result:{filename}"
            logger.info(f"Saved result to Redis '{redis_key}'.")
            return f"redis://{redis_key}"

        return filename

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

        cv_key = str(filepath).split("/")[-1].removesuffix(".json")
        res = cls.read_result_by_filename(cv_key)
        if res:
            return res
        raise FileNotFoundError(f"Result not found in database for key: {cv_key}")

    @classmethod
    def read_result_by_filename(cls, filename: str) -> dict[str, Any] | None:
        result = cv_result_cache_manager.get(filename)
        if result is not None:
            return result
            
        cv_key = filename.removesuffix(".json")
        
        try:
            with PostgresAppSession() as session:
                obj = session.query(CVResult).filter(CVResult.cv_key == cv_key).first()
                if obj and obj.raw_data:
                    data = obj.raw_data
                    cv_result_cache_manager.set(filename, data, ttl=cls.CACHE_TTL_SECONDS)
                    return data
        except Exception as exc:
            logger.warning(f"Failed reading result from Postgres for {cv_key}: {exc}")

        try:
            from app.core.config import settings
            if getattr(settings, "RESULTS_DIR", None):
                disk_file = settings.RESULTS_DIR / (filename if filename.endswith(".json") else f"{filename}.json")
                if disk_file.exists():
                    data = json.loads(disk_file.read_text(encoding="utf-8"))
                    cv_result_cache_manager.set(filename, data, ttl=cls.CACHE_TTL_SECONDS)
                    return data
        except Exception:
            pass
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
        clean_key = cv_key.strip()
        filename = f"{clean_key}.json" if not clean_key.endswith(".json") else clean_key
        stem = filename.removesuffix(".json")

        direct_res = cls.read_result_by_filename(filename)
        if direct_res and direct_res.get("status") not in ("processing", None):
            return direct_res

        stems_to_try = [stem]
        if stem.lower().startswith("cv_"):
            raw_stem = stem[3:]
            stems_to_try.extend([raw_stem, f"cv_{raw_stem}", f"CV_{raw_stem}"])
        else:
            stems_to_try.append(f"cv_{stem}")

        for s in list(stems_to_try):
            if not s.startswith("cv_document_"):
                stems_to_try.append(f"cv_document_{s}")
                if s.startswith("cv_"):
                    stems_to_try.append(f"cv_document_{s[3:]}")
            if not s.startswith("cv_candidate_"):
                stems_to_try.append(f"cv_candidate_{s}")
                if s.startswith("cv_"):
                    stems_to_try.append(f"cv_candidate_{s[3:]}")

        seen: set[str] = set()
        for s in stems_to_try:
            if s in seen:
                continue
            seen.add(s)
            fn = f"{s}.json"
            alt_res = cls.read_result_by_filename(fn)
            if alt_res and alt_res.get("status") not in ("processing", None):
                return alt_res

        matches = cls.find_results_by_scan_id(stem)
        if matches:
            for match in matches:
                try:
                    alt_res = cls.read_result(match)
                    if alt_res and alt_res.get("status") not in ("processing", None):
                        return alt_res
                except Exception as exc:
                    logger.warning(f"Failed loading matched result for stem {stem}: {exc}")

        alias_matches = cls._find_results_by_legacy_alias(stem)
        if len(alias_matches) == 1:
            return alias_matches[0]
        if len(alias_matches) > 1:
            logger.warning(f"Legacy CV key '{stem}' is ambiguous across {len(alias_matches)} canonical identities.")
            return None

        if direct_res:
            return direct_res

        return None

    @classmethod
    def exists(cls, filename: str) -> bool:
        if cv_result_cache_manager.exists(filename):
            return True
        cv_key = filename.removesuffix(".json")
        try:
            with PostgresAppSession() as session:
                return session.query(CVResult.cv_key).filter(CVResult.cv_key == cv_key).first() is not None
        except Exception:
            return False

    @classmethod
    def find_results_by_scan_id(cls, scan_id: str) -> list[str]:
        results: list[str] = []
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

        try:
            with PostgresAppSession() as session:
                target = f"%{scan_id}%"
                db_results = session.query(CVResult.cv_key, CVResult.raw_data).filter(CVResult.cv_key.ilike(target)).all()
                for row in db_results:
                    if row.raw_data and cls._result_matches_scan_id(row.raw_data, scan_id):
                        results.append(row.cv_key)
        except Exception as exc:
            logger.warning(f"DB scan failed for scan_id {scan_id}: {exc}")

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
        values_to_check = [data.get("id"), data.get("scan_id"), data.get("cv_id"), data.get("candidate_id")]
        for value in values_to_check:
            if value is None:
                continue
            normalized = str(value).removesuffix(".json").lower()
            if normalized == target or normalized.removeprefix("cv_") == target_without_prefix:
                return True
            if f"cv_document_{normalized}" == target or f"cv_document_{normalized.removeprefix('cv_')}" == target_without_prefix:
                return True
            if f"cv_candidate_{normalized}" == target or f"cv_candidate_{normalized.removeprefix('cv_')}" == target_without_prefix:
                return True
        return False

    @classmethod
    def list_all_results(cls) -> list[dict[str, Any]]:
        results_by_id: dict[str, dict[str, Any]] = {}

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

        try:
            with PostgresAppSession() as session:
                db_results = session.query(CVResult).order_by(CVResult.parsed_at.desc()).all()
                for row in db_results:
                    data = row.raw_data
                    if isinstance(data, dict):
                        item_id = str(data.get("id") or data.get("scan_id") or row.cv_key).lower()
                        if item_id not in results_by_id or (data.get("parsed_at") or "") >= (results_by_id[item_id].get("parsed_at") or ""):
                            results_by_id[item_id] = data
        except Exception as exc:
            logger.warning(f"Failed to query DB in list_all_results: {exc}")

        items = list(results_by_id.values())
        items.sort(key=lambda x: str(x.get("created_at") or x.get("parsed_at") or ""), reverse=True)
        return items
