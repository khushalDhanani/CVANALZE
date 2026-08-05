import json
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import PostgresAppSession, MssqlReadSession
from app.core.logging import logger
from app.models.domain import DepartmentDomainMaster
from app.schemas.domain import DepartmentDomain




@dataclass(frozen=True)
class DomainMatcher:
    """
    Preprocessed domain index for fast candidate matching.

    Keyword regexes are compiled once at load time and reused across every CV
    analysis, avoiding per-request re.compile and JSON parsing.
    """

    domain: DepartmentDomain
    _keyword_patterns: tuple[re.Pattern[str], ...]
    _keyword_words: frozenset[str]

    def keyword_match_count(self, text: str) -> int:
        count = 0
        for pattern in self._keyword_patterns:
            if pattern.search(text):
                count += 1
        return count

    def shares_keyword_with(self, domain_words: set[str]) -> bool:
        return bool(domain_words.intersection(self._keyword_words))


class DepartmentDomainRepository:
    """
    Repository over DepartmentDomainMaster with a thread-safe in-memory cache.

    Loading strategy:
    1. Query active rows from MSSQL (joined to OrgDepartmentMst for dept names).
    2. If the DB returns no rows, it logs a warning.

    The cache is loaded lazily on first access, reused across all requests, and
    can be reloaded via refresh_cache() (exposed through cache_warmer.warm_all).
    """

    def __init__(
        self,
        *,
        db_factory: Callable[[], Session | None] | None = None,
    ) -> None:
        self._db_factory = db_factory
        self._lock = threading.RLock()
        self._domains: list[DepartmentDomain] | None = None
        self._matchers: list[DomainMatcher] | None = None

    def get_all_domains(self) -> list[DepartmentDomain]:
        with self._lock:
            if self._domains is None:
                self._reload_locked()
            return list(self._domains or [])

    def get_domain_by_department(self, department_id: int | None) -> DepartmentDomain | None:
        if department_id is None:
            return None
        target = str(department_id)
        for domain in self.get_all_domains():
            if domain.department_id is not None and str(domain.department_id) == target:
                return domain
        return None

    def get_domain_matchers(self) -> list[DomainMatcher]:
        with self._lock:
            if self._matchers is None:
                self._reload_locked()
            return list(self._matchers or [])

    def refresh_cache(self) -> None:
        with self._lock:
            self._reload_locked()

    def _reload_locked(self) -> None:
        domains = self._load_from_db()
        source = "db"
        if not domains:
            logger.warning("[DEPARTMENT_DOMAIN] DB returned 0 domains. Application requires initialized taxonomy in Database!")
            domains = []
        self._domains = domains
        self._matchers = self._build_matchers(domains)
        logger.info(f"[DEPARTMENT_DOMAIN] Loaded {len(domains)} active domain(s) from {source}.")

    def _create_session(self) -> Session | None:
        if self._db_factory is not None:
            try:
                session = self._db_factory()
                return session if session is not None else None
            except Exception as exc:
                logger.warning(f"[DEPARTMENT_DOMAIN] DB session factory failed: {exc}")
                return None
        if PostgresAppSession is None:
            return None
        try:
            return PostgresAppSession()
        except Exception as exc:
            logger.warning(f"[DEPARTMENT_DOMAIN] Could not create DB session: {exc}")
            return None

    def _load_from_db(self) -> list[DepartmentDomain] | None:
        session = self._create_session()
        if session is None:
            return None
        try:
            stmt = (
                select(DepartmentDomainMaster)
                .where(DepartmentDomainMaster.IsActive == True)
                .order_by(
                    DepartmentDomainMaster.Priority.asc(),
                    DepartmentDomainMaster.Id.asc(),
                )
            )
            rows = session.execute(stmt).scalars().all()
            if not rows:
                return []
            return [
                DepartmentDomain(
                    id=int(row.Id),
                    department_id=(int(row.DepartmentId) if row.DepartmentId is not None else None),
                    department_name=(row.DepartmentNameSnapshot or row.DomainName),
                    domain_name=row.DomainName,
                    keywords=json.loads(row.Keywords) if row.Keywords else [],
                    default_roles=json.loads(row.DefaultRoles) if row.DefaultRoles else [],
                    priority=int(row.Priority or 0),
                    is_active=bool(row.IsActive),
                )
                for row in rows
            ]
        except Exception as exc:
            logger.warning(f"[DEPARTMENT_DOMAIN] DB load failed: {exc}")
            return None
        finally:
            session.close()



    @staticmethod
    def _build_matchers(domains: list[DepartmentDomain]) -> list[DomainMatcher]:
        return [
            DomainMatcher(
                domain=domain,
                _keyword_patterns=tuple(
                    re.compile(
                        r"(?:\b|_)" + re.escape(keyword) + r"(?:\b|_)",
                        re.IGNORECASE,
                    )
                    for keyword in domain.keywords
                ),
                _keyword_words=frozenset(domain.keywords),
            )
            for domain in domains
        ]


department_domain_repository = DepartmentDomainRepository()
