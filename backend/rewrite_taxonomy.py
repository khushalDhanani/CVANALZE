import sys
import re

with open('backend/app/services/dynamic_taxonomy_service.py', 'r') as f:
    content = f.read()

# 1. Remove _in_memory_synonyms and _initialized and _ensure_initialized and add_designation
content = re.sub(r'    _in_memory_synonyms: dict\[str, tuple\[str, str, str\]\] = \{\}\n    _initialized: bool = False\n\n    @classmethod\n    def _ensure_initialized\(cls\) -> None:.*?(?=    @classmethod\n    def _try_exact_mssql_match)', '', content, flags=re.DOTALL)

# 2. Modify check_family_compatibility
new_check = '''    @classmethod
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
            return False, 0.3
            
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
            
        return False, 0.3'''
content = re.sub(r'    @classmethod\n    def check_family_compatibility\(.*?return False, 0\.3', new_check, content, flags=re.DOTALL)

# 3. Update _try_exact_mssql_match
new_exact_match = '''    @classmethod
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
        return None'''
content = re.sub(r'    @classmethod\n    def _try_exact_mssql_match.*?return None', new_exact_match, content, flags=re.DOTALL)

# 4. Remove _get_default_fallback and replace calls
content = re.sub(r'    @classmethod\n    def _get_default_fallback.*?\n\n', '', content, flags=re.DOTALL)

fallback_replacement = '''NormalizedClassification(
            db_department_id=None,
            db_department_name=None,
            db_designation_id=None,
            db_designation_name=None,
            industry_department=None,
            industry_designation=None,
            industry_domain=None,
            match_status="NO_SUITABLE_MATCH",
            confidence=0.0,
            match_source="NO_MATCH",
            evidence=[]
        )'''
content = re.sub(r'cls\._get_default_fallback\([^)]*\)', fallback_replacement, content)

# 5. Fix vector_semantic to PostgreSQL Vector
content = content.replace('"vector_semantic"', '"PostgreSQL Vector"')
content = content.replace('source="vector_semantic"', 'source="PostgreSQL"')
content = content.replace('RuleConfigManager.get_taxonomy_rules().default_domain', 'None')
content = content.replace('industry_designation=matched_term', 'industry_designation=None')
# We need to drop import RuleConfigManager if not used anymore
content = content.replace('from app.core.rule_config_manager import RuleConfigManager\n', '')

with open('backend/app/services/dynamic_taxonomy_service.py', 'w') as f:
    f.write(content)

