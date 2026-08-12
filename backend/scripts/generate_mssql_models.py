import json
import os

with open("PR4/PR4_AIRIS_MSSQL_Metadata.json", "r") as f:
    data = json.load(f)

groups = {
    "candidate": [
        "RecruitCandidateMst", "RecruitCandidateExperienceDet",
        "RecruitCandidateQualificationDet", "RecruitCandidateSkillDet",
        "RecruitCandidateLanguageDet", "RecruitCandidateLocationMst",
        "RecruitCandidateNoticePeriodMst"
    ],
    "vacancy": [
        "RecruitVacancyRequest", "RecruitVacancyRequriedQualificationDet",
        "RecruitVacancyCandidateList", "RecruitVacancyRequestTrack",
        "RecruitVacancyCandidiateHistoryDet"
    ],
    "organization": [
        "OrgCompanyMst", "OrgLocationMst", "OrgMainDepartmentMst",
        "OrgDepartmentMst", "OrgDesignationMst", "OrgJobProfileMst",
        "JobProfileDomainKnowledgeDet", "OrgJobProfileQualificationDet",
        "OrgDesignationMappingDet", "JobProfileDepartmentDet"
    ],
    "taxonomy": [
        "RecruitDomainKnowledgeMst", "RecruitDomainKnowledgeDeptDet",
        "RecruitDomainKnowledgeSkillDet", "RecruitSkillMst",
        "RecruitSkillTypeMst", "QualificationMst", "TransactionStatusMst",
        "LanguageMst", "CityMst", "StateMst", "CountryMst",
        "OrgBusinessGroupMst", "OrgDesignationMstAether",
        "EmployeeGradeMst", "RecruitChannelMst", "RecruitChannelCategoryMst"
    ]
}

type_map = {
    "bigint": "BigInteger",
    "int": "Integer",
    "varchar": "String",
    "nvarchar": "String",
    "datetime": "DateTime",
    "date": "Date",
    "bit": "Boolean",
    "numeric": "Numeric",
    "decimal": "Numeric",
    "tinyint": "Integer",
    "smallint": "Integer"
}

table_dict = {t["table_name"]: t for t in data["tables"]}
fks_by_source_table = {}
for fk in data.get("relevant_foreign_keys", []):
    st = fk["source_table"]
    if st not in fks_by_source_table:
        fks_by_source_table[st] = []
    fks_by_source_table[st].append(fk)

for group_name, table_names in groups.items():
    imports = [
        "from __future__ import annotations",
        "from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, Date, Numeric, ForeignKey", 
        "from sqlalchemy.orm import relationship",
        "from app.core.database import MssqlReadBase"
    ]
    
    classes = []
    
    for t_name in table_names:
        if t_name not in table_dict:
            print(f"Warning: {t_name} not found in metadata")
            continue
        table = table_dict[t_name]
        
        pks = {pk["primary_key_column"] for pk in table.get("primary_keys", [])}
        fks = {fk["source_column"]: f"{fk['target_table']}.{fk['target_column']}" for fk in fks_by_source_table.get(t_name, [])}
        
        cls_lines = [f"class {t_name}(MssqlReadBase):"]
        cls_lines.append(f'    __tablename__ = "{t_name}"')
        cls_lines.append(f'    __table_args__ = {{"schema": "{table["schema_name"]}"}}')
        cls_lines.append("")
        
        for col in table["columns"]:
            c_name = col["column_name"]
            c_type = type_map.get(col["data_type"], "String")
            
            args = [c_type]
            if c_name in pks:
                args.append("primary_key=True")
                
            fk_target = fks.get(c_name)
            if fk_target:
                args.append(f'ForeignKey("{fk_target}")')
                
            cls_lines.append(f'    {c_name} = Column({", ".join(args)})')
            
        classes.append("\n".join(cls_lines))
        
    content = "\n".join(imports) + "\n\n\n" + "\n\n\n".join(classes) + "\n"
    
    with open(f"backend/app/models/mssql/{group_name}.py", "w") as f:
        f.write(content)

print("Generated models in backend/app/models/mssql/")
