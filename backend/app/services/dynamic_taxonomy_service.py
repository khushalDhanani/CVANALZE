# backend/app/services/dynamic_taxonomy_service.py
import hashlib
import logging
from typing import Any
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.database import SessionLocal, pg_SessionLocal
from app.core.rule_config_manager import RuleConfigManager
from app.models.pg import DomainEmbedding
from app.models.taxonomy import (
    DesignationMaster,
    DesignationSynonym,
    DomainMaster,
    FamilyCompatibility,
    JobFamilyMaster,
)
from app.services.domain_embedding_service import DomainEmbeddingService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger("cv_analyzer")


class DynamicTaxonomyResult(BaseModel):
    domain_id: int | None = None
    domain_name: str
    family_id: int | None = None
    family_name: str
    designation_id: int | None = None
    designation_name: str | None = None
    matched_term: str | None = None
    similarity_score: float = 1.0
    match_source: str = "database_exact"  # "database_exact", "vector_semantic", "legacy_fallback"


class DynamicTaxonomyService:
    """
    Dynamic Enterprise Taxonomy Resolution Service.
    Replaces static keyword & regex rule evaluation with:
    1. MSSQL Exact Alias / Synonym Lookups (O(1))
    2. pgvector Dense Vector Cosine Similarity (Sub-10ms)
    3. Dynamic Domain & Job Family Hierarchy Resolution
    4. Graceful Fallback to RuleConfig Defaults
    """

    @classmethod
    def resolve_candidate_role_and_domain(
        cls,
        role_or_summary: str,
        skills: list[str] | None = None,
        threshold: float = 0.70,
    ) -> DynamicTaxonomyResult:
        """
        Resolves candidate's domain, job family, and designation dynamically without hardcoded keyword lists.
        """
        clean_text = role_or_summary.strip()
        if not clean_text:
            return cls._get_default_fallback("Empty role input")

        skills_text = " ".join(skills) if skills else ""
        full_query_text = f"{clean_text} {skills_text}".strip().lower()

        # 1. Check MSSQL exact synonym / designation match
        exact_res = cls._try_exact_mssql_match(clean_text)
        if exact_res:
            return exact_res

        # 2. Check pgvector semantic similarity match
        vector_res = cls._try_vector_semantic_match(full_query_text, threshold=threshold)
        if vector_res:
            return vector_res

        # 3. Fallback to default domain
        return cls._get_default_fallback(matched_term=clean_text)

    @classmethod
    def resolve_vacancy_domain_and_family(
        cls,
        title: str,
        department: str = "",
        description: str = "",
        required_skills: list[str] | None = None,
        threshold: float = 0.70,
    ) -> DynamicTaxonomyResult:
        """
        Resolves vacancy's domain and job family dynamically using vector similarity & MSSQL taxonomy hierarchy.
        """
        clean_title = title.strip()
        if not clean_title:
            return cls._get_default_fallback("Empty vacancy title")

        # 1. Check MSSQL exact match on title
        exact_res = cls._try_exact_mssql_match(clean_title)
        if exact_res:
            return exact_res

        # 2. Vector search on combined title + department + top skills
        skills_text = " ".join(required_skills) if required_skills else ""
        query_text = f"{clean_title} {department} {skills_text}".strip().lower()
        vector_res = cls._try_vector_semantic_match(query_text, threshold=threshold)
        if vector_res:
            return vector_res

        return cls._get_default_fallback(matched_term=clean_title)

    @classmethod
    def check_family_compatibility(
        cls,
        candidate_family_name: str,
        vacancy_family_name: str,
    ) -> tuple[bool, float]:
        """
        Checks dynamic family compatibility from MSSQL family_compatibilities table.
        Returns (is_compatible, compatibility_score).
        """
        if candidate_family_name.lower().strip() == vacancy_family_name.lower().strip():
            return True, 1.0

        if SessionLocal is not None:
            try:
                with SessionLocal() as session:
                    src = session.query(JobFamilyMaster).filter(JobFamilyMaster.family_name == candidate_family_name).first()
                    tgt = session.query(JobFamilyMaster).filter(JobFamilyMaster.family_name == vacancy_family_name).first()
                    if src and tgt:
                        compat = session.query(FamilyCompatibility).filter(
                            FamilyCompatibility.source_family_id == src.family_id,
                            FamilyCompatibility.target_family_id == tgt.family_id,
                        ).first()
                        if compat:
                            return compat.is_allowed, compat.compatibility_score
            except Exception as exc:
                logger.warning(f"[DYNAMIC_TAXONOMY] Family compatibility DB query failed: {exc}")

        # Static fallback compatibility check
        compat_map = RuleConfigManager.get_taxonomy_rules().compatibility_map
        allowed_list = compat_map.get(candidate_family_name, [])
        if vacancy_family_name in allowed_list:
            return True, 1.0
        return False, 0.3

    _in_memory_synonyms: dict[str, tuple[str, str, str]] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        if cls._initialized:
            return
        cls._initialized = True
        try:
            taxonomy = RuleConfigManager.get_taxonomy_rules()
            for r in taxonomy.vacancy_rules:
                desig_name = r.name.replace("_", " ").title()
                for b in r.branches:
                    for c in b.conditions:
                        for kw in c.keywords:
                            kw_clean = kw.strip().lower()
                            if kw_clean and len(kw_clean) > 1:
                                cls._in_memory_synonyms[kw_clean] = (desig_name, r.family, r.domain)
            for r in taxonomy.candidate_rules:
                desig_name = r.name.replace("_", " ").title()
                fam_name = r.families[0] if r.families else taxonomy.default_family
                for b in r.branches:
                    for c in b.conditions:
                        for kw in c.keywords:
                            kw_clean = kw.strip().lower()
                            if kw_clean and len(kw_clean) > 1:
                                cls._in_memory_synonyms[kw_clean] = (desig_name, fam_name, r.domain)
        except Exception as exc:
            logger.warning(f"[DYNAMIC_TAXONOMY] Failed to seed default in-memory synonyms: {exc}")

    @classmethod
    def add_designation(
        cls,
        designation_name: str,
        family_name: str,
        synonyms: list[str] | None = None,
        seniority_level: str = "Standard",
    ) -> bool:
        """
        Dynamically adds a new designation and synonyms to MSSQL & generates embeddings in pgvector.
        Zero code modifications or JSON edits required!
        """
        cls._ensure_initialized()
        clean_desig = designation_name.strip()
        if not clean_desig:
            return False

        dom_name = RuleConfigManager.get_taxonomy_rules().default_domain
        if SessionLocal is not None:
            try:
                with SessionLocal() as session:
                    fam = session.query(JobFamilyMaster).filter(JobFamilyMaster.family_name == family_name).first()
                    if fam and fam.domain:
                        dom_name = fam.domain.domain_name
            except Exception:
                pass

        terms_to_register = [clean_desig] + (synonyms or [])
        for t in terms_to_register:
            cls._in_memory_synonyms[t.strip().lower()] = (clean_desig, family_name, dom_name)

        if SessionLocal is not None:
            try:
                with SessionLocal() as session:
                    fam = session.query(JobFamilyMaster).filter(JobFamilyMaster.family_name == family_name).first()
                    if fam:
                        code = clean_desig.upper().replace(" ", "_")
                        desig = session.query(DesignationMaster).filter(DesignationMaster.designation_code == code).first()
                        if not desig:
                            desig = DesignationMaster(
                                family_id=fam.family_id,
                                designation_code=code,
                                designation_name=clean_desig,
                                seniority_level=seniority_level,
                            )
                            session.add(desig)
                            session.flush()

                        # Add canonical synonym
                        canon = session.query(DesignationSynonym).filter(
                            DesignationSynonym.designation_id == desig.designation_id,
                            DesignationSynonym.synonym_text == clean_desig,
                        ).first()
                        if not canon:
                            session.add(DesignationSynonym(designation_id=desig.designation_id, synonym_text=clean_desig, is_canonical=True))

                        # Add user-provided synonyms
                        if synonyms:
                            for syn in synonyms:
                                syn_clean = syn.strip()
                                if syn_clean:
                                    syn_obj = session.query(DesignationSynonym).filter(
                                        DesignationSynonym.designation_id == desig.designation_id,
                                        DesignationSynonym.synonym_text == syn_clean,
                                    ).first()
                                    if not syn_obj:
                                        session.add(DesignationSynonym(designation_id=desig.designation_id, synonym_text=syn_clean, is_canonical=False))

                        session.commit()
            except Exception as exc:
                logger.warning(f"[DYNAMIC_TAXONOMY] MSSQL session commit failed: {exc}")

        # Vectorize designation & synonyms in pgvector
        terms_to_embed = [clean_desig] + (synonyms or [])
        for term in terms_to_embed:
            DomainEmbeddingService.get_or_generate_domain_embedding(term=term, category="job_titles", allow_live_generation=True)

        logger.info(f"[DYNAMIC_TAXONOMY] Successfully added designation '{clean_desig}'.")
        return True

    @classmethod
    def _try_exact_mssql_match(cls, term: str) -> DynamicTaxonomyResult | None:
        cls._ensure_initialized()
        clean_term = term.strip().lower()

        # Check in-memory fast registry first (longest keyword match first)
        matches: list[tuple[str, tuple[str, str, str]]] = []
        for syn_key, info in cls._in_memory_synonyms.items():
            if syn_key == clean_term or (len(syn_key) > 3 and syn_key in clean_term):
                matches.append((syn_key, info))

        if matches:
            best_key, (desig_name, fam_name, dom_name) = max(matches, key=lambda item: len(item[0]))
            return DynamicTaxonomyResult(
                domain_name=dom_name,
                family_name=fam_name,
                designation_name=desig_name,
                matched_term=best_key,
                similarity_score=1.0,
                match_source="database_exact",
            )

        if SessionLocal is None:
            return None
        try:
            with SessionLocal() as session:
                syn = session.query(DesignationSynonym).filter(DesignationSynonym.synonym_text == clean_term).first()
                if not syn:
                    # Try partial case-insensitive match
                    syn = session.query(DesignationSynonym).filter(DesignationSynonym.synonym_text.ilike(f"%{clean_term}%")).first()

                if syn and syn.designation:
                    desig = syn.designation
                    fam = desig.family
                    dom = fam.domain if fam else None

                    return DynamicTaxonomyResult(
                        domain_id=dom.domain_id if dom else None,
                        domain_name=dom.domain_name if dom else RuleConfigManager.get_taxonomy_rules().default_domain,
                        family_id=fam.family_id if fam else None,
                        family_name=fam.family_name if fam else RuleConfigManager.get_taxonomy_rules().default_family,
                        designation_id=desig.designation_id,
                        designation_name=desig.designation_name,
                        matched_term=syn.synonym_text,
                        similarity_score=1.0,
                        match_source="database_exact",
                    )
        except Exception as exc:
            logger.warning(f"[DYNAMIC_TAXONOMY] MSSQL exact lookup failed for '{term}': {exc}")
        return None

    @classmethod
    def _try_vector_semantic_match(cls, query_text: str, threshold: float = 0.70) -> DynamicTaxonomyResult | None:
        if pg_SessionLocal is None:
            return None
        try:
            query_vector = EmbeddingService.generate_embedding(query_text, identifier=f"dynamic_tax:{query_text}")
            if not query_vector:
                return None

            with pg_SessionLocal() as pg_session:
                stmt = (
                    select(DomainEmbedding.term, DomainEmbedding.embedding.cosine_distance(query_vector).label("distance"))
                    .where(DomainEmbedding.category == "job_titles")
                    .order_by("distance")
                    .limit(1)
                )
                res = pg_session.execute(stmt).first()
                if res:
                    matched_term, distance = res
                    sim_score = 1.0 - float(distance)
                    if sim_score >= threshold:
                        # Attempt to resolve matched term to MSSQL designation
                        mssql_res = cls._try_exact_mssql_match(matched_term)
                        if mssql_res:
                            mssql_res.similarity_score = round(sim_score, 4)
                            mssql_res.match_source = "vector_semantic"
                            return mssql_res
                        else:
                            return DynamicTaxonomyResult(
                                domain_name=RuleConfigManager.get_taxonomy_rules().default_domain,
                                family_name=RuleConfigManager.get_taxonomy_rules().default_family,
                                designation_name=matched_term,
                                matched_term=matched_term,
                                similarity_score=round(sim_score, 4),
                                match_source="vector_semantic",
                            )
        except Exception as exc:
            logger.warning(f"[DYNAMIC_TAXONOMY] Vector semantic lookup failed for '{query_text}': {exc}")
        return None

    @classmethod
    def _get_default_fallback(cls, matched_term: str | None = None) -> DynamicTaxonomyResult:
        tax_rules = RuleConfigManager.get_taxonomy_rules()
        return DynamicTaxonomyResult(
            domain_name=tax_rules.default_domain,
            family_name=tax_rules.default_family,
            designation_name=matched_term,
            matched_term=matched_term,
            similarity_score=0.5,
            match_source="legacy_fallback",
        )
