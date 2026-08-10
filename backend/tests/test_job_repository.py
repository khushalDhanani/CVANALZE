import pytest

from app.core.cache import vacancy_cache_manager
from app.repositories.job import JobRepository, VacancyLoadStatus, VacancySourceUnavailableError
from app.services.job_preprocessor import JobPreprocessor


@pytest.fixture(autouse=True)
def clear_job_cache():
    JobRepository.invalidate_cache()


def test_job_preprocessor_single():
    raw_job = {
        "id": "test-1",
        "title": "Senior Python Backend Developer",
        "department": "Engineering & IT",
        "required_skills": ["Python", "FastAPI", "Docker"],
        "preferred_keywords": ["Kubernetes", "PostgreSQL"],
    }

    processed = JobPreprocessor.preprocess_job(raw_job)

    assert processed["_precomputed_dept"] == "engineering & it"
    assert "python" in processed["_precomputed_title_terms"]
    assert "backend" in processed["_precomputed_title_terms"]
    assert "python" in processed["_precomputed_req_skills"]
    assert "kubernetes" in processed["_precomputed_pref_keywords"]
    assert "domain" in processed
    assert "job_family" in processed


def test_job_repository_does_not_cache_mssql_failure_as_empty(monkeypatch):
    def fail_session():
        raise RuntimeError("MSSQL offline")

    monkeypatch.setattr("app.repositories.job.MssqlReadSession", fail_session)

    with pytest.raises(VacancySourceUnavailableError):
        JobRepository.load_all_jobs()

    assert vacancy_cache_manager.get(JobRepository._VACANCY_CACHE_KEY) is None


def test_job_repository_caches_legitimate_zero_vacancies(monkeypatch):
    monkeypatch.setattr("app.repositories.job.VacancyService.get_active_vacancies", lambda _service: [])
    monkeypatch.setattr("app.repositories.job.threading.Thread.start", lambda _thread: None)

    result = JobRepository.load_all_jobs(db=object())
    cached = vacancy_cache_manager.get(JobRepository._VACANCY_CACHE_KEY)

    assert result.status == VacancyLoadStatus.EMPTY
    assert result.jobs == []
    assert cached["jobs"] == []


def test_job_repository_returns_stale_cache_on_mssql_failure(monkeypatch):
    cached_jobs = [{"id": "vacancy-1", "title": "Cached role"}]
    vacancy_cache_manager.set(JobRepository._VACANCY_CACHE_KEY, {"jobs": cached_jobs, "version": "old-version"})
    monkeypatch.setattr(JobRepository, "_is_stale", classmethod(lambda _cls, *_args, **_kwargs: True))

    def fail_query(_service):
        raise RuntimeError("MSSQL offline")

    monkeypatch.setattr("app.repositories.job.VacancyService.get_active_vacancies", fail_query)

    result = JobRepository.load_all_jobs(db=object())

    assert result.status == VacancyLoadStatus.STALE
    assert result.jobs == cached_jobs
    assert vacancy_cache_manager.get(JobRepository._VACANCY_CACHE_KEY)["jobs"] == cached_jobs


def test_job_repository_cache_hit():
    vacancy_cache_manager.delete("all_jobs")
    JobRepository._STALENESS_CACHE.clear()

    # First call: cache miss, loads & pre-processes
    jobs1 = JobRepository.get_all_jobs()
    version1 = JobRepository.get_vacancy_version()

    assert version1 != ""

    metrics1 = JobRepository.get_metrics()
    hits_before = metrics1["cache_hits"]

    # Second call: cache hit
    jobs2 = JobRepository.get_all_jobs()
    metrics2 = JobRepository.get_metrics()

    assert metrics2["cache_hits"] == hits_before + 1
    assert len(jobs1) == len(jobs2)
    assert jobs1[0]["id"] == jobs2[0]["id"]


def test_job_repository_get_job_by_id():
    jobs = JobRepository.get_all_jobs()
    sample_id = jobs[0].get("id") or jobs[0].get("vacancy_id")

    found = JobRepository.get_job_by_id(str(sample_id))

    assert found is not None
    assert str(found.get("id") or found.get("vacancy_id")) == str(sample_id)


def test_job_repository_version_hash():
    version = JobRepository.get_vacancy_version()
    assert isinstance(version, str)
    if version:
        assert len(version) == 64  # SHA256 length
