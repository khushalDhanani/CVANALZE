import json
from concurrent.futures import ThreadPoolExecutor

from app.repositories.department_domain import DepartmentDomainRepository
from app.services.scoring_engine import ScoringEngine


def _seed_repo(*, db_factory=None, seed_path=None, seed_loader=None):
    return DepartmentDomainRepository(
        db_factory=db_factory or (lambda: None),
        seed_path=seed_path,
        seed_loader=seed_loader,
    )


def test_falls_back_to_seed_when_db_unavailable():
    repo = _seed_repo(db_factory=lambda: None)
    domains = repo.get_all_domains()
    assert len(domains) == 8
    assert all(d.is_active for d in domains)
    assert domains[0].domain_name == "Information Technology & Software"
    assert domains[0].department_id == 9
    assert domains[0].department_name == "CIS Team"
    assert domains[0].priority == 1


def test_seed_matches_legacy_map_values():
    repo = _seed_repo()
    by_domain = {d.domain_name: d for d in repo.get_all_domains()}

    it = by_domain["Information Technology & Software"]
    assert it.department_id == 9
    assert it.department_name == "CIS Team"
    assert it.priority == 1
    for kw in ["developer", "flutter", "dotnet", "full stack", "ui/ux"]:
        assert kw in it.keywords
    assert it.default_roles[0] == "Software Developer"

    fin = by_domain["Finance & Accounting"]
    assert fin.department_id == 8
    assert fin.department_name == "Finance Team"
    assert fin.priority == 2
    for kw in ["finance", "tally", "ledger", "valuation"]:
        assert kw in fin.keywords


def test_get_domain_by_department():
    repo = _seed_repo()
    repo._domains = None  # force reload path
    assert repo.get_domain_by_department(99999) is None
    assert repo.get_domain_by_department(None) is None


def test_get_domain_by_department_with_custom_data():
    loader = lambda path: [
        {
            "department_id": 15,
            "department_name": "Information Technology",
            "domain_name": "Information Technology & Software",
            "keywords": ["developer"],
            "default_roles": ["Software Developer"],
            "priority": 1,
            "is_active": True,
        }
    ]
    repo = _seed_repo(seed_loader=loader)
    domain = repo.get_domain_by_department(15)
    assert domain is not None
    assert domain.department_name == "Information Technology"
    assert repo.get_domain_by_department(99) is None


def test_refresh_cache_reloads_data():
    records = [
        {
            "department_name": "Information Technology",
            "domain_name": "Information Technology & Software",
            "keywords": ["developer"],
            "default_roles": ["Software Developer"],
            "priority": 1,
            "is_active": True,
        }
    ]
    loader = lambda path: records
    repo = _seed_repo(seed_loader=loader)
    assert len(repo.get_all_domains()) == 1

    records.append(
        {
            "department_name": "Finance & Accounting",
            "domain_name": "Finance & Accounting",
            "keywords": ["ledger"],
            "default_roles": ["Accountant"],
            "priority": 2,
            "is_active": True,
        }
    )
    repo.refresh_cache()
    assert len(repo.get_all_domains()) == 2


def test_domain_matchers_are_precompiled():
    repo = _seed_repo()
    matchers = repo.get_domain_matchers()
    assert len(matchers) == 8
    it_matcher = next(m for m in matchers if m.domain.domain_name == "Information Technology & Software")
    text = "senior flutter developer with rest apis and dotnet".lower()
    assert it_matcher.keyword_match_count(text) >= 3
    assert it_matcher.shares_keyword_with({"flutter", "apache"}) is True
    assert it_matcher.shares_keyword_with({"apache", "kafka"}) is False


def test_extract_candidate_domain_profile_maps_to_real_departments(monkeypatch):
    repo = _seed_repo()
    monkeypatch.setattr(ScoringEngine, "domain_repository", repo)

    software_cv = """
    Senior Flutter & Mobile App Developer
    Skills: Flutter, Dart, React Native, REST APIs, Git, Firebase
    Education: B.Tech in Computer Science
    """
    profile = ScoringEngine.extract_candidate_domain_profile(software_cv)
    assert any(term in profile["recommended_department"] for term in ["IT & Software Services", "Software", "CIS"])
    assert any(term in profile["professional_domain"] for term in ["IT & Software Services", "Information Technology", "Software"])
    assert any(
        "Developer" in role or "Engineer" in role for role in profile["suitable_job_roles"]
    )

    finance_cv = """
    Financial Analyst | CA Inter
    Skills: Financial Modeling, Valuation, Ledger, Tally ERP, Tax Audit, Forecasting
    """
    profile = ScoringEngine.extract_candidate_domain_profile(finance_cv)
    assert any(term in profile["recommended_department"] for term in ["Finance", "Accounts"])
    assert "Finance" in profile["professional_domain"] or "Accounting" in profile["professional_domain"]

    plant_cv = """
    Mechanical Engineer - Plant Maintenance
    Skills: Boiler, PLC, SCADA, Equipment, Preventive Maintenance
    """
    profile = ScoringEngine.extract_candidate_domain_profile(plant_cv)
    assert any(term in profile["recommended_department"] for term in ["Maintenance", "Plant", "Operations"])
    assert any(term in profile["professional_domain"] for term in ["Plant", "Maintenance"])


def test_extract_candidate_domain_profile_generic_fallback(monkeypatch):
    repo = _seed_repo()
    monkeypatch.setattr(ScoringEngine, "domain_repository", repo)

    profile = ScoringEngine.extract_candidate_domain_profile("completely unrelated text about hobbies")
    assert profile["recommended_department"] == "General Engineering & Operations"
    assert profile["professional_domain"] == "General Operations"
    assert profile["suitable_job_roles"] == ["Operations Associate", "General Specialist"]


def test_new_department_works_without_code_change(monkeypatch):
    loader = lambda path: json.loads(
        path.read_text(encoding="utf-8")
    )["domains"] + [
        {
            "department_name": "Data & Analytics",
            "domain_name": "Data Science & Analytics",
            "keywords": [
                "machine learning",
                "data science",
                "tensorflow",
                "pandas",
                "deep learning",
                "nlp",
                "big data",
                "statistics",
                "data mining",
            ],
            "default_roles": ["Data Scientist", "ML Engineer", "Data Analyst"],
            "priority": 9,
            "is_active": True,
        }
    ]
    repo = _seed_repo(seed_loader=loader)
    assert len(repo.get_all_domains()) == 9
    monkeypatch.setattr(ScoringEngine, "domain_repository", repo)

    cv_text = """
    Senior Data Scientist
    Skills: Machine Learning, TensorFlow, Pandas, Deep Learning, NLP, Big Data, Statistics
    """
    profile = ScoringEngine.extract_candidate_domain_profile(cv_text)
    assert profile["recommended_department"] == "Data & Analytics"
    assert profile["professional_domain"] == "Data Science & Analytics"
    assert profile["suitable_job_roles"][0] == "Data Scientist"


def test_build_domain_candidate_text_infers_departments(monkeypatch):
    repo = _seed_repo()
    monkeypatch.setattr(ScoringEngine, "domain_repository", repo)

    domain_text = ScoringEngine._build_domain_candidate_text(
        "## Senior Flutter Developer\n"
        "### Skills\n"
        "Flutter, Dart, REST APIs"
    )
    assert "CIS Team" in domain_text


def test_thread_safety_smoke():
    repo = _seed_repo()
    errors = []

    def reader():
        try:
            for _ in range(50):
                assert len(repo.get_all_domains()) == 8
                assert len(repo.get_domain_matchers()) == 8
                assert repo.get_domain_by_department(99999) is None
        except Exception as exc:  # noqa: BLE001 - collected for thread-safety assertion
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: reader(), range(8)))
    assert errors == []
