from __future__ import annotations

from app.repositories.department_domain import DepartmentDomainRepository


def test_department_domain_repository_get_all_domains() -> None:
    repo = DepartmentDomainRepository()
    domains = repo.get_all_domains()
    assert isinstance(domains, list)
    assert len(domains) > 0
    dept_names = [d.department_name for d in domains]
    assert any("CIS" in name or "IT" in name or "Engineering" in name for name in dept_names)


def test_department_domain_repository_is_ready() -> None:
    repo = DepartmentDomainRepository()
    assert repo.is_ready() is True


def test_department_domain_repository_matchers() -> None:
    repo = DepartmentDomainRepository()
    matchers = repo.get_domain_matchers()
    assert isinstance(matchers, list)
    assert len(matchers) > 0
    # Test keyword match count for a sample tech text
    text = "Experienced software developer in flutter and dotnet applications"
    total_hits = sum(m.keyword_match_count(text) for m in matchers)
    assert total_hits > 0
