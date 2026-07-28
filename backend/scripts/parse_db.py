import json

with open("scripts/db_analysis_output.json", "r") as f:
    data = json.load(f)

fks = data["foreign_keys"]
schemas = data["schemas"]

core_tables = [
    "OrgBusinessGroupMst", "OrgCompanyMst", "OrgMainDepartmentMst",
    "OrgDepartmentMst", "OrgLocationTypeMst", "OrgLocationMst",
    "RecruitVacancyRequest"
]

print("=== Core Relationships ===")
for fk in fks:
    if fk.get("parent_table") in core_tables and fk.get("referenced_table") in core_tables:
        print(f"{fk['parent_table']}.{fk['parent_column']} -> {fk['referenced_table']}.{fk['referenced_column']}")

print("\n=== Vacancy Request Dependencies ===")
for fk in fks:
    if fk.get("parent_table") == "RecruitVacancyRequest":
        print(f"RecruitVacancyRequest.{fk['parent_column']} -> {fk['referenced_table']}.{fk['referenced_column']}")

print("\n=== Vacancy Request Columns ===")
for col in schemas.get("RecruitVacancyRequest", []):
    print(f"  {col['name']} ({col['type']})")

print("\n=== Candidate/CV Tables ===")
candidate_tables = [t for t in data["discovered_tables"] if "Candidate" in t]
print("Candidate tables:", ", ".join(candidate_tables))

for ct in candidate_tables:
    if ct in schemas:
        cols = [c["name"] for c in schemas[ct]]
        cv_cols = [c for c in cols if "CV" in c.upper() or "RESUME" in c.upper() or "FILE" in c.upper()]
        if cv_cols:
             print(f"Table {ct} has file/CV columns: {cv_cols}")
