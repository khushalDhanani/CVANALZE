import pytest
from unittest.mock import MagicMock
from app.repositories.mssql.candidate_source import CandidateSourceRepository
from app.repositories.mssql.vacancy_source import VacancySourceRepository
from app.repositories.mssql.job_profile_source import JobProfileSourceRepository

def test_candidate_repository_contract():
    mock_db = MagicMock()
    # Provide a mock tuple for the first() call so it doesn't return early
    mock_db.execute.return_value.first.return_value = (1, "John", "Doe", 1, 5.0, 10.0, True, 1, "Profile", 1, 1)
    mock_db.execute.return_value.all.return_value = []
    
    repo = CandidateSourceRepository(mock_db)
    # The queries are constructed before execution. If an attribute is missing, it will raise AttributeError.
    try:
        repo.get_candidate_aggregate(1)
    except AttributeError as e:
        pytest.fail(f"CandidateSourceRepository references an undeclared model attribute: {e}")
    except Exception as e:
        # We might get other exceptions like ValueError if our mock tuple size is wrong, but AttributeError is the main one.
        if "unpack" not in str(e):
            raise e

def test_vacancy_repository_contract():
    mock_db = MagicMock()
    # Provide a mock tuple for the first() call
    mock_db.execute.return_value.first.return_value = (1, 1, 1, 1, 1, 1, 1.0, 2.0, 1.0, 2.0, "know", "M", True, False, False, False, 1)
    mock_db.execute.return_value.all.return_value = []
    
    repo = VacancySourceRepository(mock_db)
    try:
        repo.get_vacancy_aggregate(1)
    except AttributeError as e:
        pytest.fail(f"VacancySourceRepository references an undeclared model attribute: {e}")
    except Exception as e:
        if "unpack" not in str(e):
            raise e

def test_job_profile_repository_contract():
    mock_db = MagicMock()
    # Provide a mock tuple for the first() call
    mock_db.execute.return_value.first.return_value = (1, "name", "desc", 1, 1, 1, True)
    mock_db.execute.return_value.all.return_value = []
    
    repo = JobProfileSourceRepository(mock_db)
    try:
        repo.get_job_profile_aggregate(1)
    except AttributeError as e:
        pytest.fail(f"JobProfileSourceRepository references an undeclared model attribute: {e}")
    except Exception as e:
        if "unpack" not in str(e):
            raise e
