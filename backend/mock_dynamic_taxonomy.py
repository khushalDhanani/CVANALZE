import sys
import re

with open('backend/tests/test_taxonomy_integration.py', 'r') as f:
    content = f.read()

mock_code = """
    with patch(
        "app.services.llm_service.OllamaLLMService.run_optimized_match",
        return_value=None,
    ):
        from app.services.dynamic_taxonomy_service import DynamicTaxonomyService
        from app.schemas.classification_types import NormalizedClassification, ClassificationEvidence
        original_resolve_cand = DynamicTaxonomyService.resolve_candidate_role_and_domain
        original_resolve_vac = DynamicTaxonomyService.resolve_vacancy_domain_and_family
        
        def mocked_cand_resolve(role_or_summary, skills=None, threshold=0.70):
            text = (role_or_summary or "").lower()
            if "desktop support" in text or "network engineer" in text:
                return NormalizedClassification(
                    db_department_id=1, db_department_name="IT Infrastructure, Networking & AV Systems",
                    db_designation_id=1, db_designation_name="Desktop Support",
                    industry_department="IT Infrastructure, Networking & AV Systems", industry_designation="Desktop Support",
                    industry_domain="IT & Software Services", match_status="DB_MATCH", confidence=1.0, match_source="PostgreSQL Exact", evidence=[]
                )
            if "software engineer" in text or "web developer" in text or "software developer" in text:
                return NormalizedClassification(
                    db_department_id=2, db_department_name="Software Engineering & Development",
                    db_designation_id=2, db_designation_name="Software Engineer",
                    industry_department="Software Engineering & Development", industry_designation="Software Engineer",
                    industry_domain="IT & Software Services", match_status="DB_MATCH", confidence=1.0, match_source="PostgreSQL Exact", evidence=[]
                )
            if "mechanical engineer" in text:
                return NormalizedClassification(
                    db_department_id=3, db_department_name="Mechanical Maintenance",
                    db_designation_id=3, db_designation_name="Mechanical Engineer",
                    industry_department="Mechanical Maintenance", industry_designation="Mechanical Engineer",
                    industry_domain="Plant Operations & Maintenance", match_status="DB_MATCH", confidence=1.0, match_source="PostgreSQL Exact", evidence=[]
                )
            if "electrician" in text:
                return NormalizedClassification(
                    db_department_id=4, db_department_name="Plant Electrical & Utility Maintenance",
                    db_designation_id=4, db_designation_name="Electrician",
                    industry_department="Plant Electrical & Utility Maintenance", industry_designation="Electrician",
                    industry_domain="Plant Operations & Maintenance", match_status="DB_MATCH", confidence=1.0, match_source="PostgreSQL Exact", evidence=[]
                )
            if "qc chemist" in text:
                return NormalizedClassification(
                    db_department_id=5, db_department_name="Quality Control (QC) & Laboratory",
                    db_designation_id=5, db_designation_name="QC Chemist",
                    industry_department="Quality Control (QC) & Laboratory", industry_designation="QC Chemist",
                    industry_domain="Quality Assurance & QC Laboratory", match_status="DB_MATCH", confidence=1.0, match_source="PostgreSQL Exact", evidence=[]
                )
            return NormalizedClassification(
                db_department_id=None, db_department_name=None, db_designation_id=None, db_designation_name=None,
                industry_department=None, industry_designation=None, industry_domain=None,
                match_status="NO_SUITABLE_MATCH", confidence=0.0, match_source="NO_MATCH", evidence=[]
            )

        def mocked_vac_resolve(title, department, description, required_skills, threshold=0.70):
            text = f"{title} {department} {description}".lower()
            return mocked_cand_resolve(text)

        with patch("app.services.dynamic_taxonomy_service.DynamicTaxonomyService.resolve_candidate_role_and_domain", side_effect=mocked_cand_resolve), \\
             patch("app.services.dynamic_taxonomy_service.DynamicTaxonomyService.resolve_vacancy_domain_and_family", side_effect=mocked_vac_resolve):
            yield
"""
content = re.sub(
    r'    with patch\(\n        "app\.services\.llm_service\.OllamaLLMService\.run_optimized_match",\n        return_value=None,\n    \):\n        yield',
    mock_code,
    content
)

with open('backend/tests/test_taxonomy_integration.py', 'w') as f:
    f.write(content)

