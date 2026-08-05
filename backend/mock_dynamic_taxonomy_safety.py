import sys

with open('backend/tests/test_taxonomy_integration.py', 'r') as f:
    content = f.read()

content = content.replace(
'''                return NormalizedClassification(
                    db_department_id=7, db_department_name="Fire & Safety",
                    db_designation_id=7, db_designation_name="Safety Officer",
                    industry_department="Fire & Safety", industry_designation="Safety Officer",
                    industry_domain="Environmental Health & Safety (EHS)", match_status="DB_MATCH", confidence=1.0, match_source="PostgreSQL Exact", evidence=[]
                )''',
'''                return NormalizedClassification(
                    db_department_id=7, db_department_name="Fire, Safety & EHS",
                    db_designation_id=7, db_designation_name="Safety Officer",
                    industry_department="Fire, Safety & EHS", industry_designation="Safety Officer",
                    industry_domain="Environmental Health & Safety (EHS)", match_status="DB_MATCH", confidence=1.0, match_source="PostgreSQL Exact", evidence=[]
                )'''
)

with open('backend/tests/test_taxonomy_integration.py', 'w') as f:
    f.write(content)

