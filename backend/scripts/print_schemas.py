import json

with open("scripts/db_analysis_output.json", "r") as f:
    data = json.load(f)

tables = [
    "OrgBusinessGroupMst", "OrgCompanyMst", "OrgDepartmentMst", 
    "OrgLocationMst", "OrgJobProfileMst", "OrgDesignationMst",
    "RecruitCandidateMst"
]
for t in tables:
    print(f"\n--- {t} ---")
    for col in data["schemas"].get(t, []):
        print(f"  {col['name']} ({col['type']})")
