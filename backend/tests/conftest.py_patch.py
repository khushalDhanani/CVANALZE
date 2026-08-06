from app.schemas.domain import DepartmentDomain

def get_mock_domains():
    return [
        DepartmentDomain(
            id=1, department_id=9, department_name="CIS Team", domain_name="Information Technology & Software",
            keywords=["developer", "flutter", "dotnet", "full stack", "ui/ux", "desktop support", "software engineer", "machine learning"],
            default_roles=["Software Developer"], priority=1
        ),
        DepartmentDomain(
            id=2, department_id=8, department_name="Finance Team", domain_name="Finance & Accounting",
            keywords=["finance", "tally", "ledger", "valuation"],
            default_roles=["Finance Executive"], priority=2
        ),
        DepartmentDomain(
            id=3, department_id=7, department_name="Engineering Team", domain_name="Engineering",
            keywords=["civil", "mechanical", "engineering"],
            default_roles=["Engineer"], priority=3
        ),
        DepartmentDomain(id=4, department_id=4, department_name="Sales", domain_name="Sales", keywords=["sales"], default_roles=[], priority=4),
        DepartmentDomain(id=5, department_id=5, department_name="HR", domain_name="HR", keywords=["hr"], default_roles=[], priority=5),
        DepartmentDomain(id=6, department_id=6, department_name="Operations", domain_name="Operations", keywords=["operations"], default_roles=[], priority=6),
        DepartmentDomain(id=7, department_id=7, department_name="Legal", domain_name="Legal", keywords=["legal"], default_roles=[], priority=7),
        DepartmentDomain(id=8, department_id=8, department_name="Other", domain_name="Other", keywords=["other"], default_roles=[], priority=8)
    ]
