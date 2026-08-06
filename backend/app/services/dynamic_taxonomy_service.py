from __future__ import annotations
# backend/app/services/dynamic_taxonomy_service.py
import logging

from pydantic import BaseModel
from sqlalchemy import select

from app.core.database import PostgresAppSession
from app.models.pg import DomainEmbedding
from app.models.taxonomy import (
    DesignationMaster,
    DesignationSynonym,
    JobFamilyMaster,
)
from app.services.domain_embedding_service import DomainEmbeddingService
from app.services.embedding_service import EmbeddingService
from app.schemas.classification_types import NormalizedClassification, ClassificationEvidence
from app.services.department_normalizer import DepartmentNormalizer

logger = logging.getLogger("cv_analyzer")


# Deprecated model retained for backward compatibility; new services use NormalizedClassification.


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
    ) -> NormalizedClassification:
        """
        Resolves candidate's domain, job family, and designation dynamically without hardcoded keyword lists.
        """
        clean_text = role_or_summary.strip()
        if not clean_text:
            return NormalizedClassification(
            db_department_id=None,
            db_department_name=None,
            db_designation_id=None,
            db_designation_name=None,
            industry_department=None,
            industry_designation=None,
            industry_domain=None,
            match_status="NO_MATCH",
            confidence=0.0,
            match_source="NO_MATCH",
            evidence=[]
        )

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
        return NormalizedClassification(
            db_department_id=None,
            db_department_name=None,
            db_designation_id=None,
            db_designation_name=None,
            industry_department=None,
            industry_designation=None,
            industry_domain=None,
            match_status="NO_MATCH",
            confidence=0.0,
            match_source="NO_MATCH",
            evidence=[]
        )

    @classmethod
    def resolve_vacancy_domain_and_family(
        cls,
        title: str,
        department: str = "",
        description: str = "",
        required_skills: list[str] | None = None,
        threshold: float = 0.70,
    ) -> NormalizedClassification:
        """
        Resolves vacancy's domain and job family dynamically using vector similarity & MSSQL taxonomy hierarchy.
        """
        clean_title = title.strip()
        if not clean_title:
            return NormalizedClassification(
            db_department_id=None,
            db_department_name=None,
            db_designation_id=None,
            db_designation_name=None,
            industry_department=None,
            industry_designation=None,
            industry_domain=None,
            match_status="NO_MATCH",
            confidence=0.0,
            match_source="NO_MATCH",
            evidence=[]
        )

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

        return NormalizedClassification(
            db_department_id=None,
            db_department_name=None,
            db_designation_id=None,
            db_designation_name=None,
            industry_department=None,
            industry_designation=None,
            industry_domain=None,
            match_status="NO_MATCH",
            confidence=0.0,
            match_source="NO_MATCH",
            evidence=[]
        )

    @classmethod
    def check_family_compatibility(
        cls,
        candidate_family_name: str,
        vacancy_family_name: str,
    ) -> tuple[bool, float]:
        """
        Checks dynamic family compatibility from PostgreSQL family_compatibilities table.
        Returns (is_compatible, compatibility_score).
        """
        if candidate_family_name.lower().strip() == vacancy_family_name.lower().strip():
            return True, 1.0

        from app.core.database import PostgresAppSession
        if PostgresAppSession is None:
            return False, 0.0
            
        try:
            with PostgresAppSession() as session:
                from app.models.taxonomy import JobFamilyMaster, FamilyCompatibility
                cand_fam = session.query(JobFamilyMaster).filter(JobFamilyMaster.family_name.ilike(candidate_family_name)).first()
                vac_fam = session.query(JobFamilyMaster).filter(JobFamilyMaster.family_name.ilike(vacancy_family_name)).first()
                if cand_fam and vac_fam:
                    compat = session.query(FamilyCompatibility).filter(
                        FamilyCompatibility.family_a_id == cand_fam.family_id,
                        FamilyCompatibility.family_b_id == vac_fam.family_id
                    ).first()
                    if compat:
                        return True, compat.compatibility_score
                    # Check reverse
                    compat_rev = session.query(FamilyCompatibility).filter(
                        FamilyCompatibility.family_a_id == vac_fam.family_id,
                        FamilyCompatibility.family_b_id == cand_fam.family_id
                    ).first()
                    if compat_rev:
                        return True, compat_rev.compatibility_score
        except Exception as e:
            logger.warning(f"[DYNAMIC_TAXONOMY] Failed to check compatibility: {e}")
            
        return False, 0.0

    @classmethod
    def _try_exact_mssql_match(cls, term: str) -> NormalizedClassification | None:
        clean_term = term.strip().lower()

        from app.core.database import PostgresAppSession
        if PostgresAppSession is None:
            return None
        try:
            with PostgresAppSession() as session:
                from app.models.taxonomy import DesignationSynonym
                syn = session.query(DesignationSynonym).filter(DesignationSynonym.synonym_text == clean_term).first()
                if not syn:
                    # Try partial case-insensitive match
                    syn = session.query(DesignationSynonym).filter(DesignationSynonym.synonym_text.ilike(f"%{clean_term}%")).first()

                if syn and syn.designation:
                    desig = syn.designation
                    fam = desig.family
                    dom = fam.domain if fam else None

                    # Use PostgreSQL aliases and industry mappings
                    department_name = fam.family_name if fam else None
                    designation_name = desig.designation_name
                    
                    industry_dept = DepartmentNormalizer.normalize_department(department_name)["industry_department"] if department_name else None
                    industry_desig = DepartmentNormalizer.normalize_designation(designation_name)["industry_designation"]
                    
                    return NormalizedClassification(
                        db_department_id=fam.family_id if fam else None,
                        db_department_name=department_name,
                        db_designation_id=desig.designation_id,
                        db_designation_name=designation_name,
                        industry_department=industry_dept,
                        industry_designation=industry_desig,
                        industry_domain=dom.domain_name if dom else None,
                        match_status="DB_MATCH",
                        confidence=1.0,
                        match_source="PostgreSQL Exact",
                        evidence=[
                            ClassificationEvidence(
                                source="PostgreSQL",
                                matched_term=syn.synonym_text,
                                matched_against=desig.designation_name,
                                confidence=1.0,
                            )
                        ],
                    )
        except Exception as exc:
            logger.warning(f"[DYNAMIC_TAXONOMY] PostgreSQL exact lookup failed for '{term}': {exc}")
        return None
        try:
            with PostgresAppSession() as session:
                syn = session.query(DesignationSynonym).filter(DesignationSynonym.synonym_text == clean_term).first()
                if not syn:
                    # Try partial case-insensitive match
                    syn = session.query(DesignationSynonym).filter(DesignationSynonym.synonym_text.ilike(f"%{clean_term}%")).first()

                if syn and syn.designation:
                    desig = syn.designation
                    fam = desig.family
                    dom = fam.domain if fam else None

                    return NormalizedClassification(
                        db_department_id=fam.family_id if fam else None,
                        db_department_name=fam.family_name if fam else RuleConfigManager.get_taxonomy_rules().default_family,
                        db_designation_id=desig.designation_id,
                        db_designation_name=desig.designation_name,
                        industry_department=DepartmentNormalizer.normalize_department(fam.family_name if fam else RuleConfigManager.get_taxonomy_rules().default_family)["industry_department"],
                        industry_designation=DepartmentNormalizer.normalize_designation(desig.designation_name)["industry_designation"],
                        industry_domain=dom.domain_name if dom else None,
                        match_status="DB_MATCH",
                        confidence=1.0,
                        match_source="mssql_exact",
                        evidence=[
                            ClassificationEvidence(
                                source="mssql_exact",
                                matched_term=syn.synonym_text,
                                matched_against=desig.designation_name,
                                confidence=1.0,
                            )
                        ],
                    )
        except Exception as exc:
            logger.warning(f"[DYNAMIC_TAXONOMY] MSSQL exact lookup failed for '{term}': {exc}")
        return None

    @classmethod
    def _try_vector_semantic_match(cls, query_text: str, threshold: float = 0.70) -> NormalizedClassification | None:
        if PostgresAppSession is None:
            return None
        try:
            query_vector = EmbeddingService.generate_embedding(query_text, identifier=f"dynamic_tax:{query_text}")
            if not query_vector:
                return None

            with PostgresAppSession() as pg_session:
                stmt = (
                    select(
                        DomainEmbedding.term,
                        DomainEmbedding.embedding.cosine_distance(query_vector).label("distance"),
                    )
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
                            # mssql_res is already a NormalizedClassification — enrich with vector evidence
                            return NormalizedClassification(
                                db_department_id=mssql_res.db_department_id,
                                db_department_name=mssql_res.db_department_name,
                                db_designation_id=mssql_res.db_designation_id,
                                db_designation_name=mssql_res.db_designation_name,
                                industry_department=mssql_res.industry_department,
                                industry_designation=mssql_res.industry_designation,
                                industry_domain=mssql_res.industry_domain,
                                match_status="DB_MATCH",
                                confidence=round(sim_score, 4),
                                match_source="PostgreSQL Vector",
                                evidence=[
                                    ClassificationEvidence(
                                        source="PostgreSQL Vector",
                                        matched_term=matched_term,
                                        matched_against=mssql_res.db_designation_name or matched_term,
                                        confidence=round(sim_score, 4),
                                    )
                                ],
                            )
                        else:
                            return NormalizedClassification(
                                db_department_id=None,
                                db_department_name=None,
                                db_designation_id=None,
                                db_designation_name=None,
                                industry_department=None,
                                industry_designation=None,
                                industry_domain=None,
                                match_status="NO_MATCH",
                                confidence=round(sim_score, 4),
                                match_source="PostgreSQL Vector",
                                evidence=[
                                    ClassificationEvidence(
                                        source="PostgreSQL Vector",
                                        matched_term=matched_term,
                                        matched_against=None,
                                        confidence=round(sim_score, 4),
                                    )
                                ],
                            )
        except Exception as exc:
            logger.warning(f"[DYNAMIC_TAXONOMY] Vector semantic lookup failed for '{query_text}': {exc}")
        return None

    @classmethod
    def _get_default_fallback(cls, matched_term: str | None = None) -> NormalizedClassification:
        from app.core.rule_config_manager import RuleConfigManager
        tax_rules = RuleConfigManager.get_taxonomy_rules()
        return NormalizedClassification(
            db_department_id=None,
            db_department_name=None,
            db_designation_id=None,
            db_designation_name=None,
            industry_department=None,
            industry_designation=None,
            industry_domain=tax_rules.default_domain,
            match_status="NO_MATCH",
            confidence=0.0,
            match_source="legacy_fallback",
            evidence=[
                ClassificationEvidence(
                    source="fallback",
                    matched_term=matched_term,
                    matched_against=None,
                    confidence=0.0,
                )
            ],
        )
