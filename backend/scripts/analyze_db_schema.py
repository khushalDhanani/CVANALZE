import json

from sqlalchemy import text

from app.core.database import engine


def analyze_db():
    tables_to_check = [
        'OrgBusinessGroupMst',
        'OrgCompanyMst',
        'OrgMainDepartmentMst',
        'OrgDepartmentMst',
        'OrgLocationTypeMst',
        'OrgLocationMst',
        'RecruitVacancyRequest'
    ]
    
    # We also want to discover related tables
    discover_keywords = ['Recruit', 'Vacancy', 'Requirement', 'Job', 'Desig', 'Skill', 'Qual', 'Exp']
    
    analysis = {
        'discovered_tables': [],
        'schemas': {},
        'foreign_keys': []
    }
    
    with engine.connect() as conn:
        # 1. Discover tables
        print("Discovering tables...")
        query_tables = """
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
        """
        result_tables = conn.execute(text(query_tables)).fetchall()
        
        all_tables_in_db = [row[0] for row in result_tables]
        discovered = set(tables_to_check)
        for t in all_tables_in_db:
            for kw in discover_keywords:
                if kw.lower() in t.lower():
                    discovered.add(t)
        
        analysis['discovered_tables'] = list(discovered)
        
        # 2. Get schemas for discovered tables
        print("Fetching schemas...")
        for table in analysis['discovered_tables']:
            query_cols = text("""
            SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = :table
            """)
            cols = conn.execute(query_cols, {"table": table}).fetchall()
            if cols:
                analysis['schemas'][table] = [
                    {"name": row[0], "type": row[1], "max_len": row[2], "nullable": row[3]}
                    for row in cols
                ]
            
        # 3. Get Foreign Keys for discovered tables
        print("Fetching foreign keys...")
        query_fks = text("""
        SELECT 
            fk.name AS FK_name,
            tp.name AS parent_table,
            cp.name AS parent_column,
            tr.name AS referenced_table,
            cr.name AS referenced_column
        FROM 
            sys.foreign_keys fk
        INNER JOIN 
            sys.tables tp ON fk.parent_object_id = tp.object_id
        INNER JOIN 
            sys.tables tr ON fk.referenced_object_id = tr.object_id
        INNER JOIN 
            sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
        INNER JOIN 
            sys.columns cp ON fkc.parent_column_id = cp.column_id AND fkc.parent_object_id = cp.object_id
        INNER JOIN 
            sys.columns cr ON fkc.referenced_column_id = cr.column_id AND fkc.referenced_object_id = cr.object_id
        """)
        fks = conn.execute(query_fks).fetchall()
        for row in fks:
            if row[1] in analysis['discovered_tables'] or row[3] in analysis['discovered_tables']:
                analysis['foreign_keys'].append({
                    "fk_name": row[0],
                    "parent_table": row[1],
                    "parent_column": row[2],
                    "referenced_table": row[3],
                    "referenced_column": row[4]
                })

    with open("scripts/db_analysis_output.json", "w") as f:
        json.dump(analysis, f, indent=2)
    print("Analysis saved to scripts/db_analysis_output.json")

if __name__ == "__main__":
    analyze_db()
