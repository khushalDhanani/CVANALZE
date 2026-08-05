import threading
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.logging import logger
from app.models.taxonomy import DomainMaster, JobFamilyMaster, FamilyCompatibility

# Predefined defaults for fallback and bootstrapping
DEFAULT_DOMAINS = [
    "IT & Software Services",
    "Plant Operations & Maintenance",
    "Quality Assurance & QC Laboratory",
    "Environmental Health & Safety (EHS)",
    "Process & Project Engineering",
    "Finance & Administration",
    "General Operations"
]

DEFAULT_FAMILIES = [
    ("Software Engineering & Development", "IT & Software Services"),
    ("IT Infrastructure, Networking & AV Systems", "IT & Software Services"),
    ("Plant Electrical & Utility Maintenance", "Plant Operations & Maintenance"),
    ("Control & Instrumentation (C&I)", "Plant Operations & Maintenance"),
    ("Quality Control (QC) & Laboratory", "Quality Assurance & QC Laboratory"),
    ("Quality Assurance (QA)", "Quality Assurance & QC Laboratory"),
    ("Fire, Safety & EHS", "Environmental Health & Safety (EHS)"),
    ("Process & Project Engineering", "Process & Project Engineering"),
    ("Environment & ETP Operations", "Environmental Health & Safety (EHS)"),
    ("Finance & Administration", "Finance & Administration"),
    ("General Professional", "General Operations")
]

class TaxonomyService:
    """
    Centralized service for managing dynamic Job Taxonomy (Domains and Families).
    Replaces static canonical string variables with database-backed definitions.
    """
    _lock = threading.RLock()
    _domains_cache: dict[str, DomainMaster] | None = None
    _families_cache: dict[str, JobFamilyMaster] | None = None
    _family_to_domain_map: dict[str, str] | None = None
    _compatibility_map: dict[str, set[str]] | None = None

    @classmethod
    def reload_cache(cls, db: Session | None = None) -> None:
        """Loads all domains and families from the database into in-memory cache."""
        close_session = False
        if db is None:
            if SessionLocal is None:
                logger.warning("[TAXONOMY] No DB session available to reload cache.")
                return
            db = SessionLocal()
            close_session = True

        try:
            with cls._lock:
                domains = db.execute(select(DomainMaster).where(DomainMaster.is_active == True)).scalars().all()
                if not domains:
                    logger.info("[TAXONOMY] Taxonomy tables empty. Bootstrapping defaults...")
                    cls._bootstrap_defaults(db)
                    db.commit()
                    domains = db.execute(select(DomainMaster).where(DomainMaster.is_active == True)).scalars().all()
                
                families = db.execute(select(JobFamilyMaster).where(JobFamilyMaster.is_active == True)).scalars().all()

                cls._domains_cache = {d.domain_name: d for d in domains}
                cls._families_cache = {f.family_name: f for f in families}
                
                # Build quick lookup map: family_name -> domain_name
                domain_id_to_name = {d.domain_id: d.domain_name for d in domains}
                family_id_to_name = {f.family_id: f.family_name for f in families}
                
                cls._family_to_domain_map = {
                    f.family_name: domain_id_to_name.get(f.domain_id, "Unknown")
                    for f in families
                }
                
                # Load compatibility map
                compatibilities = db.execute(select(FamilyCompatibility).where(FamilyCompatibility.is_allowed == True)).scalars().all()
                compat_map: dict[str, set[str]] = {}
                for comp in compatibilities:
                    src_name = family_id_to_name.get(comp.source_family_id)
                    tgt_name = family_id_to_name.get(comp.target_family_id)
                    if src_name and tgt_name:
                        compat_map.setdefault(src_name, set()).add(tgt_name)
                        # Add self-compatibility inherently
                        compat_map.setdefault(src_name, set()).add(src_name)
                        compat_map.setdefault(tgt_name, set()).add(tgt_name)
                
                cls._compatibility_map = compat_map
                
                logger.info(f"[TAXONOMY] Loaded {len(domains)} domains and {len(families)} families into cache.")
        except Exception as e:
            logger.error(f"[TAXONOMY] Failed to reload cache: {e}")
        finally:
            if close_session:
                db.close()

    @classmethod
    def _bootstrap_defaults(cls, db: Session) -> None:
        """Inserts default taxonomy records if the tables are empty."""
        domain_objs = {}
        for idx, d_name in enumerate(DEFAULT_DOMAINS, start=1):
            dom = DomainMaster(
                domain_code=f"DOM_{idx:03d}",
                domain_name=d_name,
                description="Auto-bootstrapped domain",
                is_active=True
            )
            db.add(dom)
            domain_objs[d_name] = dom
        
        db.flush() # To get domain_ids
        
        for idx, (f_name, d_name) in enumerate(DEFAULT_FAMILIES, start=1):
            if d_name in domain_objs:
                fam = JobFamilyMaster(
                    domain_id=domain_objs[d_name].domain_id,
                    family_code=f"FAM_{idx:03d}",
                    family_name=f_name,
                    description="Auto-bootstrapped family",
                    is_active=True
                )
                db.add(fam)

    @classmethod
    def get_domain_by_name(cls, name: str) -> Optional[DomainMaster]:
        with cls._lock:
            if cls._domains_cache is None:
                cls.reload_cache()
            return cls._domains_cache.get(name) if cls._domains_cache else None

    @classmethod
    def get_family_by_name(cls, name: str) -> Optional[JobFamilyMaster]:
        with cls._lock:
            if cls._families_cache is None:
                cls.reload_cache()
            return cls._families_cache.get(name) if cls._families_cache else None

    @classmethod
    def get_all_domains(cls) -> list[str]:
        with cls._lock:
            if cls._domains_cache is None:
                cls.reload_cache()
            return list(cls._domains_cache.keys()) if cls._domains_cache else []

    @classmethod
    def get_all_families(cls) -> list[str]:
        with cls._lock:
            if cls._families_cache is None:
                cls.reload_cache()
            return list(cls._families_cache.keys()) if cls._families_cache else []

    @classmethod
    def get_domain_for_family(cls, family_name: str) -> str:
        with cls._lock:
            if cls._family_to_domain_map is None:
                cls.reload_cache()
            return cls._family_to_domain_map.get(family_name, "Unknown") if cls._family_to_domain_map else "Unknown"

    @classmethod
    def get_compatibility_map(cls) -> dict[str, set[str]]:
        with cls._lock:
            if cls._compatibility_map is None:
                cls.reload_cache()
            return cls._compatibility_map or {}

