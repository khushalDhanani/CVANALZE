from __future__ import annotations
# backend/app/services/dynamic_taxonomy_service.py
import logging

from sqlalchemy import select

from app.core.database import PostgresAppSession
from app.models.pg import DomainEmbedding
from app.services.embedding_service import EmbeddingService
from app.schemas.classification_types import ClassificationEvidence, NormalizedClassification, MatchStatus
from app.services.department_normalizer import DepartmentNormalizer

logger = logging.getLogger("cv_analyzer")


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
            match_status=MatchStatus.INSUFFICIENT_EVIDENCE,
            confidence=0.0,
            match_source="NO_MATCH",
            evidence=[]
        )

        skills_text = " ".join(skills) if skills else ""
        full_query_text = f"{clean_text} {skills_text}".strip().lower()

        # 1. Check true MSSQL tables first
        mssql_res = cls._resolve_mssql_source_ids(clean_text)
        if mssql_res:
            return mssql_res

        # 2. Check Postgres alias mapping
        alias_res = cls._resolve_postgres_alias(clean_text)
        if alias_res:
            return alias_res

        # 3. Check pgvector semantic similarity match
        vector_res = cls._resolve_postgres_vector(full_query_text, threshold=threshold)
        if vector_res:
            return vector_res

        from app.core.database import MssqlReadSession
        fallback_status = MatchStatus.SOURCE_DATA_UNAVAILABLE if MssqlReadSession is None else MatchStatus.NO_SUITABLE_MATCH

        # 3. Fallback to default domain
        return NormalizedClassification(
            db_department_id=None,
            db_department_name=None,
            db_designation_id=None,
            db_designation_name=None,
            industry_department=None,
            industry_designation=None,
            industry_domain=None,
            match_status=fallback_status,
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
            match_status=MatchStatus.INSUFFICIENT_EVIDENCE,
            confidence=0.0,
            match_source="NO_MATCH",
            evidence=[]
        )

        # 1. Check true MSSQL tables first
        mssql_res = cls._resolve_mssql_source_ids(clean_title)
        if mssql_res:
            return mssql_res

        # 2. Check Postgres alias mapping
        alias_res = cls._resolve_postgres_alias(clean_title)
        if alias_res:
            return alias_res

        # 3. Vector search on combined title + department + top skills
        skills_text = " ".join(required_skills) if required_skills else ""
        query_text = f"{clean_title} {department} {skills_text}".strip().lower()
        vector_res = cls._resolve_postgres_vector(query_text, threshold=threshold)
        if vector_res:
            return vector_res

        from app.core.database import MssqlReadSession
        fallback_status = MatchStatus.SOURCE_DATA_UNAVAILABLE if MssqlReadSession is None else MatchStatus.NO_SUITABLE_MATCH

        return NormalizedClassification(
            db_department_id=None,
            db_department_name=None,
            db_designation_id=None,
            db_designation_name=None,
            industry_department=None,
            industry_designation=None,
            industry_domain=None,
            match_status=fallback_status,
            confidence=0.0,
            match_source="NO_MATCH",
            evidence=[]
        )

    @classmethod
    def check_family_compatibility(
        cls,
        candidate_family_name: str,
        vacancy_family_name: str,
    ) -> tuple[bool, str, float | None]:
        """
        Checks dynamic family compatibility from PostgreSQL family_compatibilities table.
        Returns (is_allowed, status, score).
        """
        if candidate_family_name.lower().strip() == vacancy_family_name.lower().strip():
            return True, "EXACT_MATCH", 1.0

        from app.core.database import PostgresAppSession
        if PostgresAppSession is None:
            return False, "NOT_CONFIGURED", None
            
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
                        return compat.is_allowed, compat.status or "CONFIGURED", compat.compatibility_score
                    # Check reverse
                    compat_rev = session.query(FamilyCompatibility).filter(
                        FamilyCompatibility.family_a_id == vac_fam.family_id,
                        FamilyCompatibility.family_b_id == cand_fam.family_id
                    ).first()
                    if compat_rev:
                        return compat_rev.is_allowed, compat_rev.status or "CONFIGURED", compat_rev.compatibility_score
        except Exception as e:
            logger.warning(f"[DYNAMIC_TAXONOMY] Failed to check compatibility: {e}")
            
        return False, "NOT_CONFIGURED", None

    @classmethod
    def _resolve_mssql_source_ids(cls, term: str) -> NormalizedClassification | None:
        if not term or not term.strip():
            return None

        # Sanitize term: take first line and cap length to max 200 chars to avoid SQL Server truncation errors
        first_line = term.strip().splitlines()[0].strip()
        if len(first_line) > 200:
            first_line = first_line[:200].strip()

        if not first_line or len(first_line) < 2:
            return None

        clean_term = first_line.lower()

        from app.core.database import MssqlReadSession
        if MssqlReadSession is None:
            return None
            
        try:
            with MssqlReadSession() as session:
                from app.models.mssql.organization import OrgDesignationMst, OrgDepartmentMst
                
                # Check MSSQL Designation EXACT Match
                matched_desig = session.query(OrgDesignationMst).filter(OrgDesignationMst.DesigName.ilike(clean_term)).first()
                
                if not matched_desig:
                    # Partial match
                    partial_matches = session.query(OrgDesignationMst).filter(OrgDesignationMst.DesigName.ilike(f"%{clean_term}%")).all()
                    
                    if len(partial_matches) == 1:
                        matched_desig = partial_matches[0]
                    elif len(partial_matches) > 1:
                        # Ambiguity rejection: if partial match gives multiple distinct designations, reject
                        logger.warning(f"[DYNAMIC_TAXONOMY] Ambiguous partial MSSQL match for '{clean_term}', rejecting.")
                        return None
                            
                if matched_desig:
                    # Fetch department if available
                    dept_id = matched_desig.DeptID
                    dept_name = None
                    if dept_id:
                        dept = session.query(OrgDepartmentMst).filter(OrgDepartmentMst.DeptID == dept_id).first()
                        if dept:
                            dept_name = dept.DeptName

                    comp_id = matched_desig.CompID
                    comp_name = None
                    if comp_id:
                        from app.models.mssql.organization import OrgCompanyMst
                        comp = session.query(OrgCompanyMst).filter(OrgCompanyMst.CompID == comp_id).first()
                        if comp:
                            comp_name = comp.CompName

                    main_dept_id = matched_desig.MainDeptID
                    main_dept_name = None
                    if main_dept_id:
                        from app.models.mssql.organization import OrgMainDepartmentMst
                        main_dept = session.query(OrgMainDepartmentMst).filter(OrgMainDepartmentMst.MainDeptID == main_dept_id).first()
                        if main_dept:
                            main_dept_name = main_dept.DeptName

                    industry_dept = DepartmentNormalizer.normalize_department(dept_name)["industry_department"] if dept_name else None
                    industry_desig = DepartmentNormalizer.normalize_designation(matched_desig.DesigName)["industry_designation"]

                    return NormalizedClassification(
                        db_company_id=comp_id,
                        db_company_name=comp_name,
                        db_main_department_id=main_dept_id,
                        db_main_department_name=main_dept_name,
                        db_department_id=dept_id,
                        db_department_name=dept_name,
                        db_designation_id=matched_desig.DesigID,
                        db_designation_name=matched_desig.DesigName,
                        industry_department=industry_dept,
                        industry_designation=industry_desig,
                        industry_domain=None,
                        match_status=MatchStatus.DB_MATCH,
                        confidence=1.0,
                        match_source="MSSQL Source IDs",
                        evidence=[
                            ClassificationEvidence(
                                source="MSSQL",
                                matched_term=clean_term,
                                matched_against=matched_desig.DesigName,
                                confidence=1.0,
                            )
                        ],
                    )
        except Exception as exc:
            logger.warning(f"[DYNAMIC_TAXONOMY] MSSQL lookup failed for '{term}': {exc}")
        return None

    @classmethod
    def _resolve_postgres_alias(cls, term: str) -> NormalizedClassification | None:
        clean_term = term.strip().lower()

        from app.core.database import PostgresAppSession
        if PostgresAppSession is None:
            return None
            
        try:
            with PostgresAppSession() as session:
                from app.models.taxonomy import DesignationSynonym
                syns = session.query(DesignationSynonym).filter(DesignationSynonym.synonym_text == clean_term).all()
                if not syns:
                    syns = session.query(DesignationSynonym).filter(DesignationSynonym.synonym_text.ilike(f"%{clean_term}%")).all()
                
                if not syns:
                    return None
                    
                if len(syns) > 1:
                    # Ambiguity rejection: if partial match gives multiple distinct designations, reject
                    desig_ids = {s.designation_id for s in syns}
                    if len(desig_ids) > 1:
                        logger.warning(f"[DYNAMIC_TAXONOMY] Ambiguous partial alias match for '{term}', rejecting.")
                        return None
                        
                syn = syns[0]
                if syn and syn.designation:
                    desig = syn.designation
                    fam = desig.family
                    dom = fam.domain if fam else None

                    department_name = fam.family_name if fam else None
                    designation_name = desig.designation_name
                    
                    industry_dept = DepartmentNormalizer.normalize_department(department_name)["industry_department"] if department_name else None
                    industry_desig = DepartmentNormalizer.normalize_designation(designation_name)["industry_designation"]
                    
                    return NormalizedClassification(
                        db_department_id=None,
                        db_department_name=None,
                        db_designation_id=None,
                        db_designation_name=None,
                        industry_department=industry_dept,
                        industry_designation=industry_desig,
                        industry_domain=dom.domain_name if dom else None,
                        match_status=MatchStatus.PARTIAL_MATCH,
                        confidence=1.0,
                        match_source="PostgreSQL Alias",
                        evidence=[
                            ClassificationEvidence(
                                source="PostgreSQL_Alias",
                                matched_term=syn.synonym_text,
                                matched_against=desig.designation_name,
                                confidence=1.0,
                            )
                        ],
                    )
        except Exception as exc:
            logger.warning(f"[DYNAMIC_TAXONOMY] PostgreSQL alias lookup failed for '{term}': {exc}")
        return None

    @classmethod
    def _resolve_postgres_vector(cls, query_text: str, threshold: float = 0.70) -> NormalizedClassification | None:
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
                        # Attempt to resolve matched term to MSSQL designation or PostgreSQL alias
                        res_classification = cls._resolve_mssql_source_ids(matched_term)
                        if not res_classification:
                            res_classification = cls._resolve_postgres_alias(matched_term)
                            
                        if res_classification:
                            # res_classification is already a NormalizedClassification — enrich with vector evidence
                            return NormalizedClassification(
                                db_department_id=res_classification.db_department_id,
                                db_department_name=res_classification.db_department_name,
                                db_designation_id=res_classification.db_designation_id,
                                db_designation_name=res_classification.db_designation_name,
                                industry_department=res_classification.industry_department,
                                industry_designation=res_classification.industry_designation,
                                industry_domain=res_classification.industry_domain,
                                match_status=MatchStatus.PARTIAL_MATCH,
                                confidence=round(sim_score, 4),
                                match_source="PostgreSQL Vector",
                                evidence=[
                                    ClassificationEvidence(
                                        source="PostgreSQL Vector",
                                        matched_term=matched_term,
                                        matched_against=res_classification.db_designation_name or matched_term,
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
                                match_status=MatchStatus.NO_SUITABLE_MATCH,
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
