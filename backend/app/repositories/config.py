from __future__ import annotations
import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.cache import config_cache_manager
from app.core.config import settings
from app.core.database import PostgresAppSession
from app.core.logging import logger
from app.models.config import SystemConfig


class ConfigRepository:
    CACHE_TTL = 3600

    @classmethod
    def get_setting(cls, key: str, default: Any = None, db: Session | None = None) -> Any:
        cached = config_cache_manager.get(key)
        if cached is not None:
            return cached

        close_session = False
        if db is None and PostgresAppSession is not None:
            try:
                db = PostgresAppSession()
                close_session = True
            except Exception as exc:
                logger.warning(f"Could not create DB session: {exc}")

        if db is not None:
            try:
                record = db.query(SystemConfig).filter(SystemConfig.setting_key == key).first()
                if record:
                    val = json.loads(record.setting_value)
                else:
                    val = getattr(settings, key, None)
                    if val is None:
                        val = default

                config_cache_manager.set(key, val, ttl=cls.CACHE_TTL)
                return val
            except Exception as exc:
                logger.warning(f"Failed to query config {key} from DB: {exc}")
                val = getattr(settings, key, default)
                config_cache_manager.set(key, val, ttl=cls.CACHE_TTL)
                return val
            finally:
                if close_session:
                    db.close()

        val = getattr(settings, key, None)
        if val is not None:
            return val
        return default

    @classmethod
    def update_setting(cls, key: str, value: Any, db: Session | None = None) -> None:
        val_str = json.dumps(value)

        close_session = False
        if db is None and PostgresAppSession is not None:
            db = PostgresAppSession()
            close_session = True

        if db is not None:
            try:
                record = db.query(SystemConfig).filter(SystemConfig.setting_key == key).first()
                if record:
                    record.setting_value = val_str
                else:
                    new_record = SystemConfig(setting_key=key, setting_value=val_str)
                    db.add(new_record)
                db.commit()
                config_cache_manager.set(key, value, ttl=cls.CACHE_TTL)
            except Exception as exc:
                logger.error(f"Failed to save config {key} to DB: {exc}")
                db.rollback()
            finally:
                if close_session:
                    db.close()
        else:
            config_cache_manager.set(key, value, ttl=cls.CACHE_TTL)
