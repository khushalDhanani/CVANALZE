-- -----------------------------------------------------------------------------------
-- MSSQL Script: check_mssql_dependencies.sql
-- Description: Identifies any lingering dependencies on the 'cvai' schema or 
--              specific legacy cvai tables before dropping the schema.
-- -----------------------------------------------------------------------------------

USE AIRIS_TEST; -- Replace with your actual DB Name if different
GO

PRINT '=========================================================';
PRINT '  Checking for active dependencies on the cvai schema    ';
PRINT '=========================================================';

-- 1. Check for Views, Procedures, Functions, or Triggers referencing 'cvai'
SELECT 
    o.name AS ObjectName,
    o.type_desc AS ObjectType,
    m.definition AS ObjectDefinition
FROM sys.sql_modules m
INNER JOIN sys.objects o ON m.object_id = o.object_id
WHERE m.definition LIKE '%cvai.%'
   OR m.definition LIKE '%cv_results%'
ORDER BY o.type_desc, o.name;

PRINT '=========================================================';
PRINT '  Checking for Foreign Key constraints referencing cvai  ';
PRINT '=========================================================';

-- 2. Check for Foreign Keys pointing to cvai schema tables
SELECT 
    fk.name AS ForeignKeyName,
    tp.name AS ParentTable,
    cp.name AS ParentColumn,
    tr.name AS ReferencedTable,
    cr.name AS ReferencedColumn
FROM sys.foreign_keys fk
INNER JOIN sys.tables tp ON fk.parent_object_id = tp.object_id
INNER JOIN sys.schemas sp ON tp.schema_id = sp.schema_id
INNER JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
INNER JOIN sys.columns cp ON fkc.parent_column_id = cp.column_id AND fkc.parent_object_id = cp.object_id
INNER JOIN sys.tables tr ON fk.referenced_object_id = tr.object_id
INNER JOIN sys.schemas sr ON tr.schema_id = sr.schema_id
INNER JOIN sys.columns cr ON fkc.referenced_column_id = cr.column_id AND fkc.referenced_object_id = cr.object_id
WHERE sr.name = 'cvai';

PRINT '=========================================================';
PRINT '  Check complete. If zero rows returned, safe to drop.   ';
PRINT '=========================================================';
