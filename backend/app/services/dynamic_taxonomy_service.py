from __future__ import annotations
# backend/app/services/dynamic_taxonomy_service.py
import hashlib
import logging
import re

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import PostgresAppSession
from app.models.pg import DomainEmbedding
from app.models.taxonomy import DesignationMaster, DesignationSynonym, JobFamilyMaster
from app.services.domain_embedding_service import DomainEmbeddingService
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
    def add_designation(
        cls,
        designation_name: str,
        family_name: str,
        synonyms: list[str] | None = None,
        seniority_level: str = "Standard",
    ) -> bool:
        """Add or update a PostgreSQL taxonomy designation and its pgvector terms."""
        clean_name = str(designation_name or "").strip()
        clean_family = str(family_name or "").strip()
        clean_seniority = str(seniority_level or "Standard").strip() or "Standard"
        if not clean_name or not clean_family or len(clean_name) > 255 or len(clean_family) > 255 or len(clean_seniority) > 50:
            return False

        clean_synonyms = list(
            dict.fromkeys(
                str(synonym).strip().lower()
                for synonym in (synonyms or [])
                if synonym and str(synonym).strip()
            )
        )
        if any(len(synonym) > 255 for synonym in clean_synonyms):
            return False

        if PostgresAppSession is None:
            logger.warning("[DYNAMIC_TAXONOMY] PostgreSQL is unavailable; designation was not written.")
            return False

        terms = list(dict.fromkeys([clean_name.lower(), *clean_synonyms]))
        try:
            embeddings = DomainEmbeddingService.get_or_generate_domain_embeddings(
                terms,
                "job_titles",
                allow_live_generation=True,
                persist_generated=False,
            )
        except Exception as exc:
            logger.error(f"[DYNAMIC_TAXONOMY] Could not generate designation embeddings for '{clean_name}': {exc}")
            return False
        if any(not embeddings.get(term) for term in terms):
            logger.warning(f"[DYNAMIC_TAXONOMY] Designation embeddings unavailable for '{clean_name}'.")
            return False

        try:
            with PostgresAppSession() as session:
                family = session.query(JobFamilyMaster).filter(func.lower(JobFamilyMaster.family_name) == clean_family.lower()).first()
                if family is None:
                    return False

                designation = session.query(DesignationMaster).filter(func.lower(DesignationMaster.designation_name) == clean_name.lower()).first()
                if designation is not None and designation.family_id != family.family_id:
                    logger.warning(f"[DYNAMIC_TAXONOMY] Designation '{clean_name}' already belongs to another job family.")
                    return False

                if designation is None:
                    base_code = re.sub(r"[^A-Z0-9]+", "_", clean_name.upper()).strip("_") or "DESIGNATION"
                    designation_code = base_code[:100]
                    code_owner = session.query(DesignationMaster).filter(DesignationMaster.designation_code == designation_code).first()
                    if code_owner is not None:
                        suffix = hashlib.sha256(f"{clean_family}:{clean_name}".encode("utf-8")).hexdigest()[:8].upper()
                        designation_code = f"{base_code[:91]}_{suffix}"
                    designation = DesignationMaster(
                        family_id=family.family_id,
                        designation_code=designation_code,
                        designation_name=clean_name,
                        seniority_level=clean_seniority,
                        is_active=True,
                    )
                    session.add(designation)
                    session.flush()
                else:
                    designation.designation_name = clean_name
                    designation.seniority_level = clean_seniority
                    designation.is_active = True

                content_hash_source = "|".join([clean_family.lower(), clean_name.lower(), clean_seniority.lower(), *sorted(clean_synonyms)])
                designation.content_hash = hashlib.sha256(content_hash_source.encode("utf-8")).hexdigest()

                existing_synonyms = session.query(DesignationSynonym).filter(func.lower(DesignationSynonym.synonym_text).in_(terms)).all()
                if any(synonym.designation_id != designation.designation_id for synonym in existing_synonyms):
                    logger.warning(f"[DYNAMIC_TAXONOMY] A synonym for '{clean_name}' is already assigned to another designation.")
                    session.rollback()
                    return False

                existing_terms = {synonym.synonym_text.strip().lower() for synonym in existing_synonyms}
                for term in terms:
                    if term not in existing_terms:
                        session.add(
                            DesignationSynonym(
                                designation_id=designation.designation_id,
                                synonym_text=term,
                                is_canonical=term == clean_name.lower(),
                            )
                        )

                vector_rows = session.query(DomainEmbedding).filter(
                    DomainEmbedding.category == "job_titles",
                    DomainEmbedding.term.in_(terms),
                ).all()
                vectors_by_term = {row.term: row for row in vector_rows}
                for term in terms:
                    content_hash = hashlib.sha256(term.encode("utf-8")).hexdigest()
                    vector_row = vectors_by_term.get(term)
                    if vector_row is None:
                        session.add(
                            DomainEmbedding(
                                category="job_titles",
                                term=term,
                                embedding=embeddings[term],
                                embedding_model_version=settings.EMBEDDING_MODEL,
                                content_hash=content_hash,
                            )
                        )
                    else:
                        vector_row.embedding = embeddings[term]
                        vector_row.embedding_model_version = settings.EMBEDDING_MODEL
                        vector_row.content_hash = content_hash

                session.commit()
                return True
        except Exception as exc:
            logger.error(f"[DYNAMIC_TAXONOMY] Failed to add PostgreSQL designation '{clean_name}': {exc}", exc_info=True)
            return False

    @classmethod
    def resolve_candidate_role_and_domain(
        cls,
        role_or_summary: str,
        skills: list[str] | None = None,
        threshold: float | None = None,
    ) -> NormalizedClassification:
        """
        Resolves candidate's domain, job family, and designation dynamically without hardcoded keyword lists.
        """
        from app.core.rule_config_manager import RuleConfigManager

        threshold = threshold if threshold is not None else RuleConfigManager.get_taxonomy_rules().semantic_match_threshold
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
        threshold: float | None = None,
        ambiguity_gap: float | None = None,
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
        from app.core.rule_config_manager import RuleConfigManager

        taxonomy_rules = RuleConfigManager.get_taxonomy_rules()
        threshold = threshold if threshold is not None else taxonomy_rules.main_department_match_threshold
        ambiguity_gap = ambiguity_gap if ambiguity_gap is not None else taxonomy_rules.hierarchy_ambiguity_gap
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

        from app.repositories.department_domain import department_domain_repository

        domain_matchers = department_domain_repository.get_domain_matchers()

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

            semantic_keywords: list[str] = []
            for matcher in domain_matchers:
                domain = matcher.domain
                configured_name = domain.department_name.strip().lower()
                configured_domain = domain.domain_name.strip().lower()
                normalized_department = str(ind_dept).strip().lower()
                is_named_department = configured_name == dept_name_clean
                is_domain_match = bool(configured_domain and normalized_department and configured_domain == normalized_department)
                if is_named_department or is_domain_match or matcher.keyword_match_count(dept_name_clean) > 0:
                    semantic_keywords.extend(domain.keywords)
                    semantic_keywords.extend(domain.default_roles)
                    semantic_keywords.extend([domain.department_name, domain.domain_name])
            semantic_keywords = list(dict.fromkeys(keyword.strip().lower() for keyword in semantic_keywords if keyword and keyword.strip()))
            stop_words = set(RuleConfigManager.get_prefilter_rules().stop_words)
            keyword_tokens = [
                token
                for keyword in semantic_keywords
                for token in keyword.split()
                if len(token) > 2 and token not in stop_words
            ]
            semantic_keywords = list(dict.fromkeys([*semantic_keywords, *keyword_tokens]))
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
                    score += taxonomy_rules.hierarchy_exact_name_score
                    reasons.append(f"Direct match on department name '{dept_name}'")

                sem_score_acc = 0.0
                seen_kws = set()
                for kw in semantic_keywords:
                    if kw in seen_kws:
                        continue
                    if kw in role_str.lower():
                        sem_score_acc += taxonomy_rules.hierarchy_role_keyword_score
                        seen_kws.add(kw)
                    elif kw in domain_str.lower():
                        sem_score_acc += taxonomy_rules.hierarchy_domain_keyword_score
                        seen_kws.add(kw)
                    elif any(kw in s for s in skills_list):
                        sem_score_acc += taxonomy_rules.hierarchy_skill_keyword_score
                        seen_kws.add(kw)
                    elif kw in cv_snippet:
                        sem_score_acc += taxonomy_rules.hierarchy_cv_keyword_score
                        seen_kws.add(kw)

                if sem_score_acc > 0:
                    semantic_score = min(taxonomy_rules.hierarchy_rule_score_cap, sem_score_acc)
                    score += semantic_score
                    reasons.append(f"Semantic match ({len(seen_kws)} keyword hit(s)) for '{dept_name}'")

                if ind_dept and ind_dept.lower() in combined_text:
                    score += taxonomy_rules.hierarchy_normalized_name_score
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
            if gap < ambiguity_gap and second["score"] > taxonomy_rules.hierarchy_ambiguity_candidate_min_score:
                return MainDepartmentClassificationResult(
                    main_department_id=None,
                    main_department_name="NO_STRONG_MAIN_DEPARTMENT_MATCH",
                    confidence=round(top_score, 2),
                    reasoning=(
                        f"Ambiguous candidate profile matching '{top['name']}' (score: {top_score:.2f}) and "
                        f"'{second['name']}' (score: {second['score']:.2f}) with gap ({gap:.2f}) below threshold ({ambiguity_gap})."
                    ),
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
        threshold: float | None = None,
        ambiguity_gap: float | None = None,
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
        from app.core.rule_config_manager import RuleConfigManager

        taxonomy_rules = RuleConfigManager.get_taxonomy_rules()
        threshold = threshold if threshold is not None else taxonomy_rules.main_department_match_threshold
        ambiguity_gap = ambiguity_gap if ambiguity_gap is not None else taxonomy_rules.hierarchy_ambiguity_gap
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
                    score += taxonomy_rules.hierarchy_exact_name_score
                    reasons.append(f"Direct match on department name '{d_name}'")
                norm_res = DepartmentNormalizer.normalize_department(d_name)
                ind_d = (norm_res.get("industry_department") or "").lower()
                if ind_d and ind_d in combined_text:
                    score += taxonomy_rules.hierarchy_normalized_name_score
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
            if gap_d < ambiguity_gap and second_d["score"] > taxonomy_rules.hierarchy_ambiguity_candidate_min_score:
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
                    score += taxonomy_rules.hierarchy_exact_name_score
                    reasons.append(f"Direct match on designation name '{ds_name}'")
                norm_res = DepartmentNormalizer.normalize_designation(ds_name)
                ind_ds = (norm_res.get("industry_designation") or "").lower()
                if ind_ds and ind_ds in combined_text:
                    score += taxonomy_rules.hierarchy_normalized_name_score
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
            if gap_ds < ambiguity_gap and second_ds["score"] > taxonomy_rules.hierarchy_ambiguity_candidate_min_score:
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
        threshold: float | None = None,
        skip_vector: bool = False,
    ) -> NormalizedClassification:
        """
        Resolves vacancy's domain and job family dynamically using vector similarity & MSSQL taxonomy hierarchy.
        Pass `skip_vector=True` during bulk preprocessing to bypass Ollama embedding lookup and avoid blocking
        per-vacancy HTTP calls to Ollama when loading the vacancy list.
        """
        from app.core.rule_config_manager import RuleConfigManager

        threshold = threshold if threshold is not None else RuleConfigManager.get_taxonomy_rules().semantic_match_threshold
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

        # 1. Fast in-memory check via DepartmentNormalizer & DepartmentDomainRepository matchers
        clean_dept = department.strip()
        skills_text = " ".join(required_skills) if required_skills else ""
        dept_norm = DepartmentNormalizer.normalize_department(clean_dept)
        title_norm = DepartmentNormalizer.normalize_designation(clean_title)
        ind_dept = dept_norm.get("industry_department")
        ind_desig = title_norm.get("industry_designation") or clean_title

        from app.repositories.department_domain import department_domain_repository
        combined_text = f"{clean_title} {clean_dept} {description} {skills_text}".lower()
        dept_scores = []
        for matcher in department_domain_repository.get_domain_matchers():
            score = matcher.keyword_match_count(combined_text)
            if score > 0:
                dept_scores.append((score, matcher.domain))

        if dept_scores:
            best_domain = max(dept_scores, key=lambda item: (item[0], -item[1].priority))[1]
            return NormalizedClassification(
                db_department_id=dept_norm.get("db_department_id") or best_domain.department_id,
                db_department_name=clean_dept or best_domain.department_name,
                db_designation_id=None,
                db_designation_name=clean_title,
                industry_department=ind_dept or best_domain.department_name,
                industry_designation=ind_desig,
                industry_domain=best_domain.domain_name,
                match_status=MatchStatus.DB_MATCH,
                confidence=1.0,
                match_source="DepartmentDomainMaster",
                evidence=[
                    ClassificationEvidence(
                        source="DepartmentDomainMaster",
                        matched_term=clean_dept or clean_title,
                        matched_against=best_domain.domain_name,
                        confidence=1.0,
                    )
                ],
            )
        elif ind_dept:
            partial_confidence = RuleConfigManager.get_taxonomy_rules().normalizer_partial_match_confidence
            return NormalizedClassification(
                db_department_id=dept_norm.get("db_department_id"),
                db_department_name=clean_dept,
                db_designation_id=None,
                db_designation_name=clean_title,
                industry_department=ind_dept,
                industry_designation=ind_desig,
                industry_domain=ind_dept,
                match_status=MatchStatus.PARTIAL_MATCH,
                confidence=partial_confidence,
                match_source="DepartmentNormalizer",
                evidence=[
                    ClassificationEvidence(
                        source="DepartmentNormalizer",
                        matched_term=clean_dept,
                        matched_against=ind_dept,
                        confidence=partial_confidence,
                    )
                ],
            )

        # 2. Check true MSSQL tables
        mssql_res = cls._resolve_mssql_source_ids(clean_title)
        if mssql_res:
            return mssql_res

        # 3. Check Postgres alias mapping
        alias_res = cls._resolve_postgres_alias(clean_title)
        if alias_res:
            return alias_res

        # 4. Vector search on combined title + department + top skills (fallback)
        # Skip during bulk preprocessing to avoid blocking on per-vacancy Ollama HTTP calls.
        if not skip_vector:
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
    def _resolve_postgres_vector(cls, query_text: str, threshold: float | None = None) -> NormalizedClassification | None:
        if threshold is None:
            from app.core.rule_config_manager import RuleConfigManager

            threshold = RuleConfigManager.get_taxonomy_rules().semantic_match_threshold
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
