import json
from typing import Any

import redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import logger
from app.models.config import SystemConfig

_redis_client = None
if settings.REDIS_URL:
    try:
        _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception:
        _redis_client = None


class ConfigRepository:
    CACHE_TTL = 3600  # 1 hour

    @classmethod
    def get_setting(
        cls, key: str, default: Any = None, db: Session | None = None
    ) -> Any:
        # Check Redis first
        if _redis_client:
            try:
                val = _redis_client.get(f"config:{key}")
                if val is not None:
                    return json.loads(val)
            except Exception as exc:
                logger.warning(f"Failed to read config {key} from Redis: {exc}")

        # Fallback to DB
        close_session = False
        if db is None and SessionLocal is not None:
            try:
                db = SessionLocal()
                close_session = True
            except Exception as exc:
                logger.warning(f"Could not create DB session: {exc}")

        if db is not None:
            try:
                record = (
                    db.query(SystemConfig).filter(SystemConfig.setting_key == key).first()
                )
                if record:
                    val = json.loads(record.setting_value)
                else:
                    if hasattr(settings, key):
                        val = getattr(settings, key)
                        if val is None:
                            val = default
                    else:
                        val = default

                # update Redis to avoid DB spam even if missing
                if _redis_client:
                    try:
                        _redis_client.setex(f"config:{key}", cls.CACHE_TTL, json.dumps(val))
                    except Exception:
                        pass
                return val
            except Exception as exc:
                logger.warning(f"Failed to query config {key} from DB: {exc}")
                
                # Cache default on error to avoid looping exceptions
                val = getattr(settings, key, default)
                if _redis_client:
                    try:
                        _redis_client.setex(f"config:{key}", cls.CACHE_TTL, json.dumps(val))
                    except Exception:
                        pass
                return val
            finally:
                if close_session:
                    db.close()

        # If not in DB or no DB configured, use python settings object if it exists
        if hasattr(settings, key):
            val = getattr(settings, key)
            if val is not None:
                return val

        return default

    @classmethod
    def update_setting(cls, key: str, value: Any, db: Session | None = None) -> None:
        val_str = json.dumps(value)

        close_session = False
        if db is None and SessionLocal is not None:
            db = SessionLocal()
            close_session = True

        if db is not None:
            try:
                record = (
                    db.query(SystemConfig).filter(SystemConfig.setting_key == key).first()
                )
                if record:
                    record.setting_value = val_str
                else:
                    new_record = SystemConfig(setting_key=key, setting_value=val_str)
                    db.add(new_record)
                db.commit()
            except Exception as exc:
                logger.error(f"Failed to save config {key} to DB: {exc}")
                db.rollback()
            finally:
                if close_session:
                    db.close()

        # Update Redis Cache
        if _redis_client:
            try:
                _redis_client.setex(f"config:{key}", cls.CACHE_TTL, val_str)
            except Exception as exc:
                logger.warning(f"Failed to update config {key} in Redis: {exc}")
