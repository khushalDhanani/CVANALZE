from __future__ import annotations
# backend/app/services/dynamic_taxonomy_service.py
import logging

from sqlalchemy import select

from app.core.database import PostgresAppSession
from app.models.pg import DomainEmbedding
from app.services.embedding_service import EmbeddingService
from app.schemas.classification_types import (
    ClassificationEvidence,
    NormalizedClassification,
    MatchStatus,
    MainDepartmentClassificationResult,
    HierarchyMatchNode,
    HierarchyClassificationResult,
)
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
    def classify_main_department(
        cls,
        role_or_summary: str = "",
        skills: list[str] | None = None,
        domain: str | None = None,
        experience_years: float | None = None,
        cv_text: str | None = None,
        threshold: float = 0.55,
        ambiguity_gap: float = 0.05,
        main_departments: list[Any] | None = None,
        db_session: Any = None,
    ) -> MainDepartmentClassificationResult:
        """
        Data-driven & embedding-based classification of candidate profiles against active OrgMainDepartmentMst records.

        Steps:
        1. Build embeddings for active Main Departments using `MainDeptID + MainDeptName + taxonomy/keywords`.
        2. Build CV professional-profile embedding from role, skills, domain, seniority, and experience.
        3. Compare CV embedding against Main Department embeddings using cosine similarity via EmbeddingService.
        4. Apply similarity threshold and ambiguity gap checks across Top-K candidates.
        5. If vector embedding is unavailable/offline, fall back gracefully to rule-based semantic matching.
        """
        depts_to_evaluate: list[dict[str, Any]] = []

        if main_departments is not None:
            for md in main_departments:
                if isinstance(md, dict):
                    m_id = md.get("id") or md.get("MainDeptID")
                    m_name = md.get("name") or md.get("DeptName")
                else:
                    m_id = getattr(md, "MainDeptID", getattr(md, "id", None))
                    m_name = getattr(md, "DeptName", getattr(md, "name", None))
                if m_id is not None and m_name:
                    depts_to_evaluate.append({"id": int(m_id), "name": str(m_name).strip()})
        elif db_session is not None:
            from app.models.mssql.organization import OrgMainDepartmentMst
            try:
                rows = db_session.query(OrgMainDepartmentMst).filter(
                    (OrgMainDepartmentMst.IsActive == True) | (OrgMainDepartmentMst.IsActive.is_(None))
                ).all()
                for r in rows:
                    depts_to_evaluate.append({"id": int(r.MainDeptID), "name": str(r.DeptName).strip()})
            except Exception as e:
                logger.warning(f"[DYNAMIC_TAXONOMY] Failed to query OrgMainDepartmentMst from db_session: {e}")
        else:
            from app.core.cache import master_data_cache_manager
            cached_depts = master_data_cache_manager.get("main_departments")
            if cached_depts and isinstance(cached_depts, list):
                for md in cached_depts:
                    m_id = md.get("id") or md.get("MainDeptID")
                    m_name = md.get("name") or md.get("DeptName")
                    if m_id is not None and m_name:
                        depts_to_evaluate.append({"id": int(m_id), "name": str(m_name).strip()})

            if not depts_to_evaluate:
                from app.core.database import MssqlReadSession
                if MssqlReadSession is not None:
                    try:
                        with MssqlReadSession() as session:
                            from app.models.mssql.organization import OrgMainDepartmentMst
                            rows = session.query(OrgMainDepartmentMst).filter(
                                (OrgMainDepartmentMst.IsActive == True) | (OrgMainDepartmentMst.IsActive.is_(None))
                            ).all()
                            for r in rows:
                                depts_to_evaluate.append({"id": int(r.MainDeptID), "name": str(r.DeptName).strip()})
                    except Exception as e:
                        logger.warning(f"[DYNAMIC_TAXONOMY] Failed to query OrgMainDepartmentMst from MssqlReadSession: {e}")

        if not depts_to_evaluate:
            return MainDepartmentClassificationResult(
                main_department_id=None,
                main_department_name="NO_STRONG_MAIN_DEPARTMENT_MATCH",
                confidence=0.0,
                reasoning="No active main departments found in OrgMainDepartmentMst.",
                match_status="NO_STRONG_MAIN_DEPARTMENT_MATCH",
            )

        role_str = (role_or_summary or "").strip()
        domain_str = (domain or "").strip()
        skills_list = [s.strip().lower() for s in (skills or []) if s and isinstance(s, str)]
        cv_snippet = (cv_text or "")[:1000].lower()

        combined_text = f"{role_str} {domain_str} {' '.join(skills_list)} {cv_snippet}".strip().lower()
        if not combined_text:
            return MainDepartmentClassificationResult(
                main_department_id=None,
                main_department_name="NO_STRONG_MAIN_DEPARTMENT_MATCH",
                confidence=0.0,
                reasoning="Insufficient candidate profile evidence provided.",
                match_status="NO_STRONG_MAIN_DEPARTMENT_MATCH",
            )

        INTERNAL_NAME_SEMANTIC_MAP: dict[str, list[str]] = {
            "cis team": ["software", "developer", "flutter", "react", "node", "python", ".net", "c#", "java", "frontend", "backend", "full stack", "devops", "cloud", "cis", "it", "information technology", "systems", "web", "programmer", "software engineer"],
            "quality control": ["quality control", "qc", "qc chemist", "lab chemist", "analytical", "microbiology", "testing", "lab analyst", "qc executive", "qa", "quality assurance", "validation", "lab assistant"],
            "manufacturing": ["manufacturing", "production", "plant", "chemical operator", "process engineer", "maintenance", "shopfloor", "production executive", "factory", "plant engineer", "production engineer"],
            "research & development": ["research", "r&d", "formulation", "synthesis", "chemist", "scientist", "research associate", "organic chemistry", "analytical r&d"],
            "human resources": ["human resources", "hr", "talent acquisition", "recruiter", "payroll", "people ops", "hr executive", "hr manager"],
            "finance & accounts": ["finance", "accounts", "chartered accountant", "ca", "audit", "taxation", "billing", "bookkeeping", "financial analyst", "accountant"],
            "supply chain": ["supply chain", "logistics", "warehouse", "procurement", "purchase", "inventory", "vendor", "dispatch"],
            "sales & marketing": ["sales", "business development", "marketing", "commercial", "account manager", "sales executive"],
        }

        # 1. Build Candidate Professional Profile Text & Embedding
        skills_str = ", ".join(skills_list[:15]) if skills_list else ""
        cand_profile_text = (
            f"Candidate Professional Role: {role_str}. "
            f"Professional Domain: {domain_str}. "
            f"Seniority Experience: {experience_years or 0} years. "
            f"Core Technical & Functional Skills: {skills_str}. "
            f"Experience Summary: {cv_snippet[:400]}"
        ).strip()

        cand_vector: list[float] | None = None
        try:
            from app.core.config import settings
            cand_vector = EmbeddingService.generate_embedding(
                cand_profile_text,
                model_version=settings.EMBEDDING_MODEL,
                identifier=f"cand_main_dept_prof:{hash(cand_profile_text)}",
            )
        except Exception as exc:
            logger.warning(f"[DYNAMIC_TAXONOMY] Could not generate CV profile vector: {exc}")

        dept_scores: list[dict[str, Any]] = []

        for dept in depts_to_evaluate:
            dept_id = dept["id"]
            dept_name = dept["name"]
            dept_name_clean = dept_name.lower().strip()

            norm_info = DepartmentNormalizer.normalize_department(dept_name)
            ind_dept = norm_info.get("industry_department") or ""

            semantic_keywords = list(INTERNAL_NAME_SEMANTIC_MAP.get(dept_name_clean, []))
            if not semantic_keywords:
                for key_dept, kw_list in INTERNAL_NAME_SEMANTIC_MAP.items():
                    if key_dept in dept_name_clean or dept_name_clean in key_dept:
                        semantic_keywords.extend(kw_list)
            kw_str = ", ".join(semantic_keywords[:12]) if semantic_keywords else ""

            dept_profile_text = (
                f"Main Department ID: {dept_id}. "
                f"Department Name: {dept_name}. "
                f"Industry Classification: {ind_dept}. "
                f"Functions and Keywords: {kw_str}."
            ).strip()

            dept_vector: list[float] | None = None
            if cand_vector:
                try:
                    from app.core.config import settings
                    dept_vector = EmbeddingService.generate_embedding(
                        dept_profile_text,
                        model_version=settings.EMBEDDING_MODEL,
                        identifier=f"main_dept_prof:{dept_id}:{dept_name_clean}",
                    )
                except Exception as exc:
                    logger.warning(f"[DYNAMIC_TAXONOMY] Could not generate dept vector for '{dept_name}': {exc}")

            vector_sim: float | None = None
            if cand_vector and dept_vector:
                vector_sim = EmbeddingService.cosine_similarity(cand_vector, dept_vector)
                vector_sim = max(0.0, min(1.0, float(vector_sim)))

            # Direct/Rule Fallback Score
            score = 0.0
            reasons: list[str] = []

            if vector_sim is not None and vector_sim > 0.0:
                score = vector_sim
                reasons.append(f"Vector similarity ({vector_sim:.2f}) with Main Department '{dept_name}' (ID: {dept_id})")
            else:
                # Rule-based fallback if vector service is offline
                if dept_name_clean in combined_text:
                    score += 0.50
                    reasons.append(f"Direct match on department name '{dept_name}'")

                sem_score_acc = 0.0
                seen_kws = set()
                for kw in semantic_keywords:
                    if kw in seen_kws:
                        continue
                    if kw in role_str.lower():
                        sem_score_acc += 0.25
                        seen_kws.add(kw)
                    elif kw in domain_str.lower():
                        sem_score_acc += 0.20
                        seen_kws.add(kw)
                    elif any(kw in s for s in skills_list):
                        sem_score_acc += 0.15
                        seen_kws.add(kw)
                    elif kw in cv_snippet:
                        sem_score_acc += 0.10
                        seen_kws.add(kw)

                if sem_score_acc > 0:
                    semantic_score = min(0.80, sem_score_acc)
                    score += semantic_score
                    reasons.append(f"Semantic match ({len(seen_kws)} keyword hit(s)) for '{dept_name}'")

                if ind_dept and ind_dept.lower() in combined_text:
                    score += 0.25
                    reasons.append(f"Industry normalized department '{ind_dept}' matched candidate profile")

            dept_scores.append({
                "id": dept_id,
                "name": dept_name,
                "score": min(1.0, score),
                "reasons": reasons,
            })

        dept_scores.sort(key=lambda d: d["score"], reverse=True)

        if not dept_scores or dept_scores[0]["score"] == 0.0:
            return MainDepartmentClassificationResult(
                main_department_id=None,
                main_department_name="NO_STRONG_MAIN_DEPARTMENT_MATCH",
                confidence=0.0,
                reasoning="No semantic alignment found with any active Main Department.",
                match_status="NO_STRONG_MAIN_DEPARTMENT_MATCH",
            )

        top = dept_scores[0]
        top_score = top["score"]

        # Ambiguity Gap Check
        if len(dept_scores) > 1:
            second = dept_scores[1]
            gap = top_score - second["score"]
            if gap < ambiguity_gap and second["score"] > 0.35:
                return MainDepartmentClassificationResult(
                    main_department_id=None,
                    main_department_name="NO_STRONG_MAIN_DEPARTMENT_MATCH",
                    confidence=round(top_score, 2),
                    reasoning=f"Ambiguous candidate profile matching '{top['name']}' (score: {top_score:.2f}) and '{second['name']}' (score: {second['score']:.2f}) with gap ({gap:.2f}) below threshold ({ambiguity_gap}).",
                    match_status="NO_STRONG_MAIN_DEPARTMENT_MATCH",
                )

        # Confidence Threshold Check
        if top_score < threshold:
            return MainDepartmentClassificationResult(
                main_department_id=None,
                main_department_name="NO_STRONG_MAIN_DEPARTMENT_MATCH",
                confidence=round(top_score, 2),
                reasoning=f"Candidate alignment score ({top_score:.2f}) for '{top['name']}' is below required threshold ({threshold}).",
                match_status="NO_STRONG_MAIN_DEPARTMENT_MATCH",
            )

        reason_summary = "; ".join(top["reasons"]) if top["reasons"] else f"Strong alignment with {top['name']}"
        return MainDepartmentClassificationResult(
            main_department_id=top["id"],
            main_department_name=top["name"],
            confidence=round(top_score, 2),
            reasoning=f"Mapped to Main Department '{top['name']}' (ID: {top['id']}): {reason_summary}.",
            match_status="MATCHED",
        )

    @classmethod
    def invalidate_hierarchy_embeddings(cls) -> None:
        """
        Invalidates master-data organization hierarchy cache when organization master data changes.
        """
        from app.core.cache import master_data_cache_manager
        master_data_cache_manager.delete("main_departments")
        master_data_cache_manager.delete("departments")
        master_data_cache_manager.delete("designations")
        logger.info("[DYNAMIC_TAXONOMY] Master organization hierarchy cache invalidated.")

    @classmethod
    def classify_organization_hierarchy(
        cls,
        role_or_summary: str = "",
        skills: list[str] | None = None,
        domain: str | None = None,
        experience_years: float | None = None,
        cv_text: str | None = None,
        threshold: float = 0.55,
        ambiguity_gap: float = 0.05,
        main_departments: list[Any] | None = None,
        departments: list[Any] | None = None,
        designations: list[Any] | None = None,
        db_session: Any = None,
    ) -> HierarchyClassificationResult:
        """
        Hierarchy-constrained semantic mapping:
        OrgMainDepartmentMst -> OrgDepartmentMst -> OrgDesignationMst

        Rules:
        1. Resolves valid MainDeptID first.
        2. Compares ONLY Departments (OrgDepartmentMst) belonging to resolved MainDeptID.
        3. Compares ONLY Designations (OrgDesignationMst) belonging to resolved MainDeptID + DeptID.
        4. Never searches all Departments/Designations globally once parent hierarchy is known.
        5. Validates final resolved hierarchy via OrganizationSourceRepository.validate_hierarchy().
        6. Caches master-data embeddings by ID + profile hash + model version.
        """
        main_dept_res = cls.classify_main_department(
            role_or_summary=role_or_summary,
            skills=skills,
            domain=domain,
            experience_years=experience_years,
            cv_text=cv_text,
            threshold=threshold,
            ambiguity_gap=ambiguity_gap,
            main_departments=main_departments,
            db_session=db_session,
        )

        main_dept_node = HierarchyMatchNode(
            id=main_dept_res.main_department_id,
            name=main_dept_res.main_department_name,
            confidence=main_dept_res.confidence,
            reasoning=main_dept_res.reasoning,
            match_status=main_dept_res.match_status,
            top_k_candidates=[{
                "id": main_dept_res.main_department_id,
                "name": main_dept_res.main_department_name,
                "score": main_dept_res.confidence,
            }] if main_dept_res.main_department_id is not None else [],
        )

        if main_dept_res.match_status != "MATCHED" or main_dept_res.main_department_id is None:
            return HierarchyClassificationResult(
                main_department=main_dept_node,
                department=HierarchyMatchNode(
                    id=None,
                    name="NO_STRONG_DEPARTMENT_MATCH",
                    confidence=0.0,
                    reasoning="Main department was not matched; department search skipped.",
                    match_status="NO_STRONG_DEPARTMENT_MATCH",
                ),
                designation=HierarchyMatchNode(
                    id=None,
                    name="NO_STRONG_DESIGNATION_MATCH",
                    confidence=0.0,
                    reasoning="Main department was not matched; designation search skipped.",
                    match_status="NO_STRONG_DESIGNATION_MATCH",
                ),
                is_hierarchy_valid=True,
                validation_errors=[],
                overall_confidence=main_dept_res.confidence,
            )

        resolved_main_dept_id = main_dept_res.main_department_id

        # Step 2: Fetch and Constrain Departments belonging to resolved_main_dept_id
        depts_to_eval: list[dict[str, Any]] = []

        if departments is not None:
            for d in departments:
                if isinstance(d, dict):
                    m_id = d.get("main_department_id") or d.get("MainDeptID")
                    d_id = d.get("id") or d.get("DeptID")
                    d_name = d.get("name") or d.get("DeptName")
                else:
                    m_id = getattr(d, "MainDeptID", getattr(d, "main_department_id", None))
                    d_id = getattr(d, "DeptID", getattr(d, "id", None))
                    d_name = getattr(d, "DeptName", getattr(d, "name", None))
                if m_id == resolved_main_dept_id and d_id is not None and d_name:
                    depts_to_eval.append({"id": int(d_id), "name": str(d_name).strip(), "main_dept_id": m_id})
        elif db_session is not None:
            from app.models.mssql.organization import OrgDepartmentMst
            try:
                rows = db_session.query(OrgDepartmentMst).filter(
                    OrgDepartmentMst.MainDeptID == resolved_main_dept_id,
                    (OrgDepartmentMst.DeptIsActive == True) | (OrgDepartmentMst.DeptIsActive.is_(None)),
                ).all()
                for r in rows:
                    depts_to_eval.append({"id": int(r.DeptID), "name": str(r.DeptName).strip(), "main_dept_id": r.MainDeptID})
            except Exception as e:
                logger.warning(f"[DYNAMIC_TAXONOMY] Failed to query OrgDepartmentMst: {e}")
        else:
            from app.core.database import MssqlReadSession
            if MssqlReadSession is not None:
                try:
                    with MssqlReadSession() as session:
                        from app.models.mssql.organization import OrgDepartmentMst
                        rows = session.query(OrgDepartmentMst).filter(
                            OrgDepartmentMst.MainDeptID == resolved_main_dept_id,
                            (OrgDepartmentMst.DeptIsActive == True) | (OrgDepartmentMst.DeptIsActive.is_(None)),
                        ).all()
                        for r in rows:
                            depts_to_eval.append({"id": int(r.DeptID), "name": str(r.DeptName).strip(), "main_dept_id": r.MainDeptID})
                except Exception as e:
                    logger.warning(f"[DYNAMIC_TAXONOMY] Failed to query OrgDepartmentMst from MssqlReadSession: {e}")

        role_str = (role_or_summary or "").strip()
        domain_str = (domain or "").strip()
        skills_list = [s.strip().lower() for s in (skills or []) if s and isinstance(s, str)]
        cv_snippet = (cv_text or "")[:1000].lower()
        combined_text = f"{role_str} {domain_str} {' '.join(skills_list)} {cv_snippet}".strip().lower()

        if not depts_to_eval:
            dept_node = HierarchyMatchNode(
                id=None,
                name="NO_STRONG_DEPARTMENT_MATCH",
                confidence=0.0,
                reasoning=f"No active departments belong to resolved Main Dept ID {resolved_main_dept_id}.",
                match_status="NO_STRONG_DEPARTMENT_MATCH",
            )
            desig_node = HierarchyMatchNode(
                id=None,
                name="NO_STRONG_DESIGNATION_MATCH",
                confidence=0.0,
                reasoning="Department was not matched; designation search skipped.",
                match_status="NO_STRONG_DESIGNATION_MATCH",
            )
            return HierarchyClassificationResult(
                main_department=main_dept_node,
                department=dept_node,
                designation=desig_node,
                is_hierarchy_valid=True,
                validation_errors=[],
                overall_confidence=main_dept_res.confidence,
            )

        # Build candidate vector
        cand_vector: list[float] | None = None
        skills_str = ", ".join(skills_list[:15]) if skills_list else ""
        cand_profile_text = (
            f"Candidate Professional Role: {role_str}. Domain: {domain_str}. "
            f"Seniority: {experience_years or 0} yrs. Skills: {skills_str}. Summary: {cv_snippet[:400]}"
        ).strip()
        try:
            from app.core.config import settings
            cand_vector = EmbeddingService.generate_embedding(
                cand_profile_text,
                model_version=settings.EMBEDDING_MODEL,
                identifier=f"cand_prof_vector:{hash(cand_profile_text)}",
            )
        except Exception as exc:
            logger.warning(f"[DYNAMIC_TAXONOMY] Vector embedding generation error: {exc}")

        # Evaluate constrained departments
        dept_scores: list[dict[str, Any]] = []
        for d in depts_to_eval:
            d_id = d["id"]
            d_name = d["name"]
            d_name_clean = d_name.lower().strip()

            d_profile_text = (
                f"Department ID: {d_id}. Department Name: {d_name}."
            )
            d_vector: list[float] | None = None
            if cand_vector:
                try:
                    from app.core.config import settings
                    d_vector = EmbeddingService.generate_embedding(
                        d_profile_text,
                        model_version=settings.EMBEDDING_MODEL,
                        identifier=f"master_sub_dept_emb:{settings.EMBEDDING_MODEL}:{resolved_main_dept_id}:{d_id}:{hash(d_profile_text)}",
                    )
                except Exception as exc:
                    logger.warning(f"[DYNAMIC_TAXONOMY] Could not embed dept '{d_name}': {exc}")

            sim: float | None = None
            if cand_vector and d_vector:
                sim = max(0.0, min(1.0, float(EmbeddingService.cosine_similarity(cand_vector, d_vector))))

            score = 0.0
            reasons = []
            if sim is not None and sim > 0.0:
                score = sim
                reasons.append(f"Vector similarity ({sim:.2f}) with Department '{d_name}'")
            else:
                if d_name_clean in combined_text or any(part in combined_text for part in d_name_clean.split() if len(part) >= 3):
                    score += 0.60
                    reasons.append(f"Direct match on department name '{d_name}'")
                norm_res = DepartmentNormalizer.normalize_department(d_name)
                ind_d = (norm_res.get("industry_department") or "").lower()
                if ind_d and ind_d in combined_text:
                    score += 0.40
                    reasons.append(f"Industry normalized match '{ind_d}'")

            dept_scores.append({
                "id": d_id,
                "name": d_name,
                "score": min(1.0, score),
                "reasons": reasons,
            })

        dept_scores.sort(key=lambda item: item["score"], reverse=True)
        top_k_depts = dept_scores[:3]

        top_d = dept_scores[0]
        top_d_score = top_d["score"]

        # Department Ambiguity & Threshold Check
        dept_is_ambiguous = False
        if len(dept_scores) > 1:
            second_d = dept_scores[1]
            gap_d = top_d_score - second_d["score"]
            if gap_d < ambiguity_gap and second_d["score"] > 0.35:
                dept_is_ambiguous = True

        if top_d_score < threshold or dept_is_ambiguous:
            reason_msg = (
                f"Ambiguous match across departments under '{main_dept_res.main_department_name}' with top gap below threshold."
                if dept_is_ambiguous
                else f"Department score ({top_d_score:.2f}) for '{top_d['name']}' below threshold ({threshold})."
            )
            dept_node = HierarchyMatchNode(
                id=None,
                name="NO_STRONG_DEPARTMENT_MATCH",
                confidence=round(top_d_score, 2),
                reasoning=reason_msg,
                match_status="NO_STRONG_DEPARTMENT_MATCH",
                top_k_candidates=top_k_depts,
            )
            desig_node = HierarchyMatchNode(
                id=None,
                name="NO_STRONG_DESIGNATION_MATCH",
                confidence=0.0,
                reasoning="Department was not matched; designation search skipped.",
                match_status="NO_STRONG_DESIGNATION_MATCH",
            )
            return HierarchyClassificationResult(
                main_department=main_dept_node,
                department=dept_node,
                designation=desig_node,
                is_hierarchy_valid=True,
                validation_errors=[],
                overall_confidence=round((main_dept_node.confidence + dept_node.confidence) / 2, 2),
            )

        resolved_dept_id = top_d["id"]
        resolved_dept_name = top_d["name"]
        dept_node = HierarchyMatchNode(
            id=resolved_dept_id,
            name=resolved_dept_name,
            confidence=round(top_d_score, 2),
            reasoning=f"Mapped to Department '{resolved_dept_name}' (ID: {resolved_dept_id}): {'; '.join(top_d['reasons'])}.",
            match_status="MATCHED",
            top_k_candidates=top_k_depts,
        )

        # Step 3: Fetch and Constrain Designations belonging to resolved_main_dept_id + resolved_dept_id
        desigs_to_eval: list[dict[str, Any]] = []

        if designations is not None:
            for ds in designations:
                if isinstance(ds, dict):
                    m_id = ds.get("main_department_id") or ds.get("MainDeptID")
                    d_id = ds.get("department_id") or ds.get("DeptID")
                    ds_id = ds.get("id") or ds.get("DesigID")
                    ds_name = ds.get("name") or ds.get("DesigName")
                else:
                    m_id = getattr(ds, "MainDeptID", getattr(ds, "main_department_id", None))
                    d_id = getattr(ds, "DeptID", getattr(ds, "department_id", None))
                    ds_id = getattr(ds, "DesigID", getattr(ds, "id", None))
                    ds_name = getattr(ds, "DesigName", getattr(ds, "name", None))
                if m_id == resolved_main_dept_id and d_id == resolved_dept_id and ds_id is not None and ds_name:
                    desigs_to_eval.append({
                        "id": int(ds_id),
                        "name": str(ds_name).strip(),
                        "dept_id": d_id,
                        "main_dept_id": m_id,
                    })
        elif db_session is not None:
            from app.models.mssql.organization import OrgDesignationMst
            try:
                rows = db_session.query(OrgDesignationMst).filter(
                    OrgDesignationMst.MainDeptID == resolved_main_dept_id,
                    OrgDesignationMst.DeptID == resolved_dept_id,
                    (OrgDesignationMst.DesigIsActive == True) | (OrgDesignationMst.DesigIsActive.is_(None)),
                ).all()
                for r in rows:
                    desigs_to_eval.append({"id": int(r.DesigID), "name": str(r.DesigName).strip(), "dept_id": r.DeptID, "main_dept_id": r.MainDeptID})
            except Exception as e:
                logger.warning(f"[DYNAMIC_TAXONOMY] Failed to query OrgDesignationMst: {e}")
        else:
            from app.core.database import MssqlReadSession
            if MssqlReadSession is not None:
                try:
                    with MssqlReadSession() as session:
                        from app.models.mssql.organization import OrgDesignationMst
                        rows = session.query(OrgDesignationMst).filter(
                            OrgDesignationMst.MainDeptID == resolved_main_dept_id,
                            OrgDesignationMst.DeptID == resolved_dept_id,
                            (OrgDesignationMst.DesigIsActive == True) | (OrgDesignationMst.DesigIsActive.is_(None)),
                        ).all()
                        for r in rows:
                            desigs_to_eval.append({"id": int(r.DesigID), "name": str(r.DesigName).strip(), "dept_id": r.DeptID, "main_dept_id": r.MainDeptID})
                except Exception as e:
                    logger.warning(f"[DYNAMIC_TAXONOMY] Failed to query OrgDesignationMst from MssqlReadSession: {e}")

        if not desigs_to_eval:
            desig_node = HierarchyMatchNode(
                id=None,
                name="NO_STRONG_DESIGNATION_MATCH",
                confidence=0.0,
                reasoning=f"No active designations belong to Department ID {resolved_dept_id}.",
                match_status="NO_STRONG_DESIGNATION_MATCH",
            )
            return HierarchyClassificationResult(
                main_department=main_dept_node,
                department=dept_node,
                designation=desig_node,
                is_hierarchy_valid=True,
                validation_errors=[],
                overall_confidence=round((main_dept_node.confidence + dept_node.confidence) / 2, 2),
            )

        # Evaluate constrained designations
        desig_scores: list[dict[str, Any]] = []
        for ds in desigs_to_eval:
            ds_id = ds["id"]
            ds_name = ds["name"]
            ds_name_clean = ds_name.lower().strip()

            ds_profile_text = (
                f"Designation ID: {ds_id}. Designation Name: {ds_name}."
            )
            ds_vector: list[float] | None = None
            if cand_vector:
                try:
                    from app.core.config import settings
                    ds_vector = EmbeddingService.generate_embedding(
                        ds_profile_text,
                        model_version=settings.EMBEDDING_MODEL,
                        identifier=f"master_desig_emb:{settings.EMBEDDING_MODEL}:{resolved_main_dept_id}:{resolved_dept_id}:{ds_id}:{hash(ds_profile_text)}",
                    )
                except Exception as exc:
                    logger.warning(f"[DYNAMIC_TAXONOMY] Could not embed designation '{ds_name}': {exc}")

            sim: float | None = None
            if cand_vector and ds_vector:
                sim = max(0.0, min(1.0, float(EmbeddingService.cosine_similarity(cand_vector, ds_vector))))

            score = 0.0
            reasons = []
            if sim is not None and sim > 0.0:
                score = sim
                reasons.append(f"Vector similarity ({sim:.2f}) with Designation '{ds_name}'")
            else:
                if ds_name_clean in combined_text:
                    score += 0.65
                    reasons.append(f"Direct match on designation name '{ds_name}'")
                norm_res = DepartmentNormalizer.normalize_designation(ds_name)
                ind_ds = (norm_res.get("industry_designation") or "").lower()
                if ind_ds and ind_ds in combined_text:
                    score += 0.35
                    reasons.append(f"Industry normalized designation match '{ind_ds}'")

            desig_scores.append({
                "id": ds_id,
                "name": ds_name,
                "score": min(1.0, score),
                "reasons": reasons,
            })

        desig_scores.sort(key=lambda item: item["score"], reverse=True)
        top_k_desigs = desig_scores[:3]

        top_ds = desig_scores[0]
        top_ds_score = top_ds["score"]

        # Designation Ambiguity & Threshold Check
        desig_is_ambiguous = False
        if len(desig_scores) > 1:
            second_ds = desig_scores[1]
            gap_ds = top_ds_score - second_ds["score"]
            if gap_ds < ambiguity_gap and second_ds["score"] > 0.35:
                desig_is_ambiguous = True

        if top_ds_score < threshold or desig_is_ambiguous:
            reason_msg = (
                f"Ambiguous match across designations under '{resolved_dept_name}' with gap below threshold."
                if desig_is_ambiguous
                else f"Designation score ({top_ds_score:.2f}) for '{top_ds['name']}' below threshold ({threshold})."
            )
            desig_node = HierarchyMatchNode(
                id=None,
                name="NO_STRONG_DESIGNATION_MATCH",
                confidence=round(top_ds_score, 2),
                reasoning=reason_msg,
                match_status="NO_STRONG_DESIGNATION_MATCH",
                top_k_candidates=top_k_desigs,
            )
            return HierarchyClassificationResult(
                main_department=main_dept_node,
                department=dept_node,
                designation=desig_node,
                is_hierarchy_valid=True,
                validation_errors=[],
                overall_confidence=round((main_dept_node.confidence + dept_node.confidence) / 2, 2),
            )

        resolved_desig_id = top_ds["id"]
        resolved_desig_name = top_ds["name"]
        desig_node = HierarchyMatchNode(
            id=resolved_desig_id,
            name=resolved_desig_name,
            confidence=round(top_ds_score, 2),
            reasoning=f"Mapped to Designation '{resolved_desig_name}' (ID: {resolved_desig_id}): {'; '.join(top_ds['reasons'])}.",
            match_status="MATCHED",
            top_k_candidates=top_k_desigs,
        )

        # Step 4: Parent-Child Hierarchy Validation via OrganizationSourceRepository
        is_valid_hierarchy = True
        validation_errors: list[str] = []
        if db_session is not None:
            from app.repositories.mssql.organization_source import OrganizationSourceRepository
            repo = OrganizationSourceRepository(db_session)
            val_res = repo.validate_hierarchy(
                main_dept_id=resolved_main_dept_id,
                dept_id=resolved_dept_id,
                desig_id=resolved_desig_id,
            )
            if not val_res.get("is_valid"):
                is_valid_hierarchy = False
                validation_errors = val_res.get("errors") or ["Parent-child hierarchy mismatch detected."]
                desig_node = HierarchyMatchNode(
                    id=None,
                    name="NO_STRONG_DESIGNATION_MATCH",
                    confidence=0.0,
                    reasoning=f"Hierarchy validation failed: {'; '.join(validation_errors)}",
                    match_status="NO_STRONG_DESIGNATION_MATCH",
                    top_k_candidates=top_k_desigs,
                )

        overall_conf = round(
            (main_dept_node.confidence + dept_node.confidence + (desig_node.confidence if desig_node.id else 0.0)) /
            (3.0 if desig_node.id else 2.0),
            2
        )

        return HierarchyClassificationResult(
            main_department=main_dept_node,
            department=dept_node,
            designation=desig_node,
            is_hierarchy_valid=is_valid_hierarchy,
            validation_errors=validation_errors,
            overall_confidence=overall_conf,
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
