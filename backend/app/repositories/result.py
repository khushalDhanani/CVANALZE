from __future__ import annotations
import json
from pathlib import Path
from typing import Any


from sqlalchemy import text
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
    def _extract_canonical_business_payload(cls, data: dict[str, Any]) -> dict[str, Any]:
        resume_json = data.get("resume_json") if isinstance(data.get("resume_json"), dict) else {}
        match_analysis = data.get("match_analysis") if isinstance(data.get("match_analysis"), dict) else {}
        exp_summary = data.get("experience_summary") if isinstance(data.get("experience_summary"), dict) else {}
        
        return {
            "result_generation_id": str(data.get("result_generation_id") or ""),
            "generation_sequence": int(data.get("generation_sequence")) if data.get("generation_sequence") is not None else None,
            "document_hash": str(data.get("cv_hash") or data.get("document_hash") or ""),
            "schema_version": str(data.get("schema_version") or ""),
            "experience_version": str(data.get("experience_version") or ""),
            "taxonomy_version": str(data.get("taxonomy_version") or ""),
            "matching_version": str(data.get("matching_version") or ""),
            "parser_version": str(data.get("parser_version") or ""),
            "full_name": str(data.get("full_name") or data.get("candidate_name") or ""),
            "email": str(data.get("email") or ""),
            "phone": str(data.get("phone") or ""),
            "location": str(data.get("location") or ""),
            "job_title": str(data.get("job_title") or ""),
            "company_name": str(data.get("company_name") or ""),
            "status": str(data.get("status") or ""),
            "experience_years": data.get("experience_years"),
            "total_experience_years": data.get("total_experience_years"),
            "total_experience_months": data.get("total_experience_months"),
            "experience_state": str(data.get("experience_state") or ""),
            "gross_display": str(data.get("gross_display") or ""),
            "seniority": str(data.get("seniority") or ""),
            "department": str(data.get("department") or match_analysis.get("primary_department") or ""),
            "domain": str(data.get("domain") or match_analysis.get("domain") or ""),
            "designation": str(data.get("designation") or (match_analysis.get("best_match") or {}).get("job_title") or ""),
            "work_experience": data.get("work_experience") or exp_summary.get("normalized_employment") or [],
            "experience_summary": exp_summary,
            "experience_gap_analysis": data.get("experience_gap_analysis") or exp_summary.get("gap_analysis") or {},
            "candidate_analysis": data.get("candidate_analysis") or match_analysis.get("candidate_analysis") or {},
            "vacancy_matches": data.get("vacancy_matches") or match_analysis.get("rankings") or match_analysis.get("best_match") or {},
            "recommendations": data.get("recommendations") or match_analysis.get("recommendations") or [],
        }

    @classmethod
    def compute_payload_checksum(cls, data: dict[str, Any]) -> str:
        import hashlib
        canonical = cls._extract_canonical_business_payload(data)
        normalized_json = json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(normalized_json.encode("utf-8")).hexdigest()

    @classmethod
    def fetch_next_generation_sequence(cls) -> int:
        with PostgresAppSession() as session:
            val = session.execute(text("SELECT nextval('cv_results_generation_seq')")).scalar()
            if val is not None:
                return int(val)
            raise RuntimeError("PostgreSQL sequence cv_results_generation_seq returned None.")


    @classmethod
    def ensure_canonical_metadata(cls, data: dict[str, Any], assign_generation_sequence: bool = False) -> dict[str, Any]:
        import time
        from datetime import datetime, timezone
        from app.core.config import settings
        now_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        if "result_generation_id" not in data or not data["result_generation_id"]:
            data["result_generation_id"] = f"gen_{now_ts}"

        if assign_generation_sequence and ("generation_sequence" not in data or not data["generation_sequence"]):
            data["generation_sequence"] = cls.fetch_next_generation_sequence()

        data["schema_version"] = data.get("schema_version") or settings.EXTRACTION_SCHEMA_VERSION
        data["document_hash"] = data.get("cv_hash") or data.get("document_hash") or ""
        data["experience_version"] = data.get("experience_version") or getattr(settings, "EXPERIENCE_CALCULATOR_VERSION", "2.0.0")
        data["taxonomy_version"] = data.get("taxonomy_version") or getattr(settings, "TAXONOMY_VERSION", "1.5.0")
        data["matching_version"] = data.get("matching_version") or getattr(settings, "MATCHING_VERSION", "2.1.0")
        data["updated_at"] = data.get("updated_at") or data.get("parsed_at") or data.get("created_at") or datetime.now(timezone.utc).isoformat()
        data["payload_checksum"] = cls.compute_payload_checksum(data)
        return data

    @classmethod
    def is_generation_current(cls, cv_key: str, incoming_generation: str, incoming_sequence: int | None = None, resource: str = "cache") -> bool:
        try:
            with PostgresAppSession() as session:
                obj = session.query(CVResult).filter(CVResult.cv_key == cv_key).first()
                if obj:
                    stored_gen = str(obj.raw_data.get("result_generation_id") if isinstance(obj.raw_data, dict) else "") or ""
                    stored_seq = int(getattr(obj, "generation_sequence", None) or (obj.raw_data.get("generation_sequence") if isinstance(obj.raw_data, dict) else 0) or 0)
                    
                    if incoming_sequence is None:
                        try:
                            parts = str(incoming_generation).split("_")
                            if len(parts) >= 2 and parts[1].isdigit():
                                incoming_sequence = int(parts[1])
                        except Exception:
                            incoming_sequence = 0
                    
                    if stored_seq > 0 and incoming_sequence is not None and incoming_sequence > 0 and incoming_sequence < stored_seq:
                        logger.warning(
                            f"[STALE_GENERATION_WRITE_REJECTED] resource={resource} cv_key='{cv_key}' "
                            f"incoming_generation={incoming_generation} (seq={incoming_sequence}) "
                            f"current_generation={stored_gen} (seq={stored_seq})"
                        )
                        return False
        except Exception as exc:
            logger.debug(f"is_generation_current check error for {cv_key}: {exc}")
        return True

    @classmethod
    def save_result(cls, filename: str, data: dict[str, Any]) -> str:
        return cls.atomic_save_result(filename, data)

    @classmethod
    def atomic_save_result(cls, filename: str, data: dict[str, Any]) -> str:
        cls.ensure_canonical_metadata(data)
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
                if result_obj and result_obj.raw_data and isinstance(result_obj.raw_data, dict):
                    existing_data = result_obj.raw_data
                    existing_gen = str(existing_data.get("result_generation_id") or "")
                    existing_seq = int(getattr(result_obj, "generation_sequence", None) or existing_data.get("generation_sequence") or 0)

                    if existing_gen and ("result_generation_id" not in data or not data["result_generation_id"] or data.get("original_status") == "CACHE_HIT"):
                        data["result_generation_id"] = existing_gen
                        data["generation_sequence"] = existing_seq or data.get("generation_sequence")
                        data["payload_checksum"] = cls.compute_payload_checksum(data)

                    new_gen = str(data.get("result_generation_id") or "")
                    new_seq = int(data.get("generation_sequence") or 0)

                    # Stale worker write rejection guard: incoming_sequence < stored_sequence
                    if existing_seq > 0 and new_seq > 0 and new_seq < existing_seq and existing_gen != new_gen:
                        logger.warning(
                            f"[STALE_GENERATION_WRITE_REJECTED] resource=cv_results cv_key='{cv_key}' "
                            f"incoming_generation={new_gen} (seq={new_seq}) current_generation={existing_gen} (seq={existing_seq})"
                        )
                        return f"redis://cv_result:{filename}"

                if not result_obj:
                    result_obj = CVResult(cv_key=cv_key)
                    session.add(result_obj)

                result_obj.status = status
                result_obj.full_name = full_name
                result_obj.candidate_id = candidate_id
                result_obj.cv_id = cv_id
                result_obj.cv_hash = cv_hash
                if "generation_sequence" in data and data["generation_sequence"] not in (None, ""):
                    result_obj.generation_sequence = int(data["generation_sequence"])
                result_obj.resume_json = resume_json
                result_obj.match_analysis = match_analysis
                result_obj.text_content = text_content
                result_obj.markdown_content = markdown_content

                session.flush()
                session.refresh(result_obj)
                if getattr(result_obj, "generation_sequence", None) is not None:
                    data["generation_sequence"] = int(result_obj.generation_sequence)

                result_obj.raw_data = data
                session.commit()
                logger.info(f"Atomically saved result to PostgreSQL 'cv_results' for cv_key '{cv_key}' (gen={data.get('result_generation_id')}, seq={data.get('generation_sequence')}).")
        except Exception as exc:
            logger.error(f"Failed to save CV result {cv_key} to PostgreSQL: {exc}")



        cv_result_cache_manager.set(filename, data, ttl=cls.CACHE_TTL_SECONDS)
        for legacy_key in data.get("legacy_cv_keys") or []:
            CacheIndex.add("cv_legacy_alias", str(legacy_key).lower(), filename)

        try:
            from app.core.config import settings
            if getattr(settings, "RESULTS_DIR", None):
                disk_file = settings.RESULTS_DIR / (filename if filename.endswith(".json") else f"{filename}.json")
                disk_file.parent.mkdir(parents=True, exist_ok=True)
                disk_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as disk_err:
            logger.warning(f"Could not write disk fallback for '{filename}': {disk_err}")

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
        cv_key = filename.removesuffix(".json")
        redis_data = cv_result_cache_manager.get(filename)

        db_data = None
        try:
            with PostgresAppSession() as session:
                obj = session.query(CVResult).filter(CVResult.cv_key == cv_key).first()
                if obj and obj.raw_data and isinstance(obj.raw_data, dict):
                    db_data = obj.raw_data
                    gen_seq = getattr(obj, "generation_sequence", None)
                    if gen_seq and "generation_sequence" not in db_data:
                        db_data["generation_sequence"] = gen_seq

        except Exception as exc:
            logger.warning(f"Failed reading result from Postgres for {cv_key}: {exc}")

        if db_data:
            cls.ensure_canonical_metadata(db_data)
            db_gen = db_data.get("result_generation_id")
            db_seq = db_data.get("generation_sequence")
            db_chk = db_data.get("payload_checksum")

            if redis_data:
                r_gen = redis_data.get("result_generation_id")
                r_seq = redis_data.get("generation_sequence")
                r_chk = redis_data.get("payload_checksum")
                r_schema = redis_data.get("schema_version")
                r_doc_hash = redis_data.get("document_hash") or redis_data.get("cv_hash")
                r_exp_ver = redis_data.get("experience_version")
                r_tax_ver = redis_data.get("taxonomy_version")
                r_match_ver = redis_data.get("matching_version")

                db_schema = db_data.get("schema_version")
                db_doc_hash = db_data.get("document_hash") or db_data.get("cv_hash")
                db_exp_ver = db_data.get("experience_version")
                db_tax_ver = db_data.get("taxonomy_version")
                db_match_ver = db_data.get("matching_version")

                metadata_matches = (
                    (r_gen == db_gen if (r_gen and db_gen) else True)
                    and (r_seq == db_seq if (r_seq and db_seq) else True)
                    and (r_chk == db_chk if (r_chk and db_chk) else True)
                    and (r_schema == db_schema if (r_schema and db_schema) else True)
                    and (r_doc_hash == db_doc_hash if (r_doc_hash and db_doc_hash) else True)
                    and (r_exp_ver == db_exp_ver if (r_exp_ver and db_exp_ver) else True)
                    and (r_tax_ver == db_tax_ver if (r_tax_ver and db_tax_ver) else True)
                    and (r_match_ver == db_match_ver if (r_match_ver and db_match_ver) else True)
                )

                if metadata_matches:
                    logger.info(
                        f"[RESULT_PARITY] cv_key={cv_key} redis_generation={r_gen} db_generation={db_gen} "
                        f"redis_seq={r_seq} db_seq={db_seq} redis_checksum={r_chk[:12] if r_chk else 'NONE'} db_checksum={db_chk[:12] if db_chk else 'NONE'} action=HIT"
                    )
                    return redis_data
                else:
                    logger.warning(
                        f"[RESULT_PARITY] cv_key={cv_key} redis_generation={r_gen} db_generation={db_gen} "
                        f"redis_seq={r_seq} db_seq={db_seq} redis_checksum={r_chk[:12] if r_chk else 'NONE'} db_checksum={db_chk[:12] if db_chk else 'NONE'} action=REHYDRATE"
                    )
                    cv_result_cache_manager.delete(filename)
                    cv_result_cache_manager.set(filename, db_data, ttl=cls.CACHE_TTL_SECONDS)
                    return db_data
            else:
                logger.info(
                    f"[RESULT_PARITY] cv_key={cv_key} redis_generation=NONE db_generation={db_gen} "
                    f"redis_seq=NONE db_seq={db_seq} redis_checksum=NONE db_checksum={db_chk[:12] if db_chk else 'NONE'} action=REHYDRATE"
                )
                cv_result_cache_manager.set(filename, db_data, ttl=cls.CACHE_TTL_SECONDS)
                return db_data

        if redis_data:
            cls.ensure_canonical_metadata(redis_data)
            return redis_data


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
                        db_ts = str(data.get("updated_at") or data.get("parsed_at") or data.get("created_at") or "")
                        redis_item = results_by_id.get(item_id)
                        redis_ts = str((redis_item or {}).get("updated_at") or (redis_item or {}).get("parsed_at") or (redis_item or {}).get("created_at") or "") if redis_item else ""
                        if item_id not in results_by_id or db_ts >= redis_ts:
                            results_by_id[item_id] = data
                            # Sync cache parity
                            fn = f"{row.cv_key}.json" if not row.cv_key.endswith(".json") else row.cv_key
                            cv_result_cache_manager.set(fn, data, ttl=cls.CACHE_TTL_SECONDS)
        except Exception as exc:
            logger.warning(f"Failed to query DB in list_all_results: {exc}")


        items = list(results_by_id.values())
        items.sort(key=lambda x: str(x.get("created_at") or x.get("parsed_at") or ""), reverse=True)
        return items
