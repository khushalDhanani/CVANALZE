import pytest
from unittest.mock import MagicMock
from sqlalchemy.orm import configure_mappers

from app.repositories.mssql.candidate_source import CandidateSourceRepository
from app.repositories.mssql.vacancy_source import VacancySourceRepository
from app.repositories.mssql.job_profile_source import JobProfileSourceRepository

from app.models.mssql.candidate import (
    RecruitCandidateMst,
    RecruitCandidateExperienceDet,
    RecruitCandidateQualificationDet,
    RecruitCandidateSkillDet,
    RecruitCandidateLanguageDet,
    RecruitCandidateLocationMst,
    RecruitCandidateNoticePeriodMst
)
from app.models.mssql.organization import (
    OrgJobProfileMst,
    OrgJobProfileQualificationDet,
    JobProfileDomainKnowledgeDet,
    OrgCompanyMst,
    OrgDepartmentMst,
    OrgDesignationMst,
    OrgLocationMst
)
from app.models.mssql.taxonomy import (
    RecruitSkillMst,
    LanguageMst,
    RecruitDomainKnowledgeMst,
    QualificationMst,
    TransactionStatusMst
)
from app.models.mssql.vacancy import (
    RecruitVacancyRequest,
    RecruitVacancyRequriedQualificationDet,
    RecruitVacancyRequestTrack,
    RecruitVacancyCandidateList,
    RecruitVacancyCandidiateHistoryDet
)


def test_models_configure_mappers():
    # Acceptance criteria: run configure_mappers()
    configure_mappers()


def test_candidate_repository_fields_exist():
    # RecruitCandidateMst
    assert hasattr(RecruitCandidateMst, "CandidateID")
    assert hasattr(RecruitCandidateMst, "CandidateFirstName")
    assert hasattr(RecruitCandidateMst, "CandidateLastName")
    assert hasattr(RecruitCandidateMst, "CandidateJobProfileID")
    assert hasattr(RecruitCandidateMst, "CandidateTotExperience")
    assert hasattr(RecruitCandidateMst, "CandidateExpectedCtc")
    assert hasattr(RecruitCandidateMst, "CandidateIsActive")
    assert hasattr(RecruitCandidateMst, "CandidateStatusID")
    assert hasattr(RecruitCandidateMst, "CandidateDomainKnowlgID")
    assert hasattr(RecruitCandidateMst, "NoticePeriodID")

    # RecruitCandidateQualificationDet
    assert hasattr(RecruitCandidateQualificationDet, "QualificationID")
    assert hasattr(RecruitCandidateQualificationDet, "CandidateID")
    assert hasattr(RecruitCandidateQualificationDet, "CandidQualiIsActive")
    assert hasattr(RecruitCandidateQualificationDet, "CandidQualiIsDeleted")

    # RecruitCandidateSkillDet
    assert hasattr(RecruitCandidateSkillDet, "SkillID")
    assert hasattr(RecruitCandidateSkillDet, "CandidateID")
    assert hasattr(RecruitCandidateSkillDet, "IsActive")

    # RecruitCandidateExperienceDet
    assert hasattr(RecruitCandidateExperienceDet, "CandidExpDetID")
    assert hasattr(RecruitCandidateExperienceDet, "CandidateID")
    assert hasattr(RecruitCandidateExperienceDet, "CandidExpIsActive")
    assert hasattr(RecruitCandidateExperienceDet, "CandidExpIsDeleted")

    # RecruitCandidateLanguageDet
    assert hasattr(RecruitCandidateLanguageDet, "LanguageID")
    assert hasattr(RecruitCandidateLanguageDet, "CandidateID")
    assert hasattr(RecruitCandidateLanguageDet, "LanguageIsDeleted")

    # RecruitCandidateLocationMst
    assert hasattr(RecruitCandidateLocationMst, "LocID")
    assert hasattr(RecruitCandidateLocationMst, "CandidateID")
    assert hasattr(RecruitCandidateLocationMst, "IsActive")


def test_vacancy_repository_fields_exist():
    # RecruitVacancyRequest
    assert hasattr(RecruitVacancyRequest, "VacancyRequestID")
    assert hasattr(RecruitVacancyRequest, "JobProfileID")
    assert hasattr(RecruitVacancyRequest, "RequestForCompID")
    assert hasattr(RecruitVacancyRequest, "RequestForDeptID")
    assert hasattr(RecruitVacancyRequest, "RequestForLocationID")
    assert hasattr(RecruitVacancyRequest, "RequestForDesigID")
    assert hasattr(RecruitVacancyRequest, "RequestedExperienceRangeFrom")
    assert hasattr(RecruitVacancyRequest, "RequestedExperienceRangeTo")
    assert hasattr(RecruitVacancyRequest, "RequestedCTCRangeFrom")
    assert hasattr(RecruitVacancyRequest, "RequestedCTCRangeTo")
    assert hasattr(RecruitVacancyRequest, "RequestedAdditionalKnowledge")
    assert hasattr(RecruitVacancyRequest, "PreferedGender")
    assert hasattr(RecruitVacancyRequest, "VacancyRequestIsActive")
    assert hasattr(RecruitVacancyRequest, "VacancyRequestIsDeleted")
    assert hasattr(RecruitVacancyRequest, "VacancyRequestClose")
    assert hasattr(RecruitVacancyRequest, "VacancyRequestIsForceClosed")
    assert hasattr(RecruitVacancyRequest, "RequestStatusID")

    # RecruitVacancyRequriedQualificationDet
    assert hasattr(RecruitVacancyRequriedQualificationDet, "RequriedQualificationID")
    assert hasattr(RecruitVacancyRequriedQualificationDet, "VacancyRequestID")

    # RecruitVacancyRequestTrack
    assert hasattr(RecruitVacancyRequestTrack, "VacancyTrackID")
    assert hasattr(RecruitVacancyRequestTrack, "VacancyRequestID")
    assert hasattr(RecruitVacancyRequestTrack, "VacancyReqIsDeleted")

    # RecruitVacancyCandidateList
    assert hasattr(RecruitVacancyCandidateList, "VacancyCandidateID")
    assert hasattr(RecruitVacancyCandidateList, "VacancyRequestID")

    # RecruitVacancyCandidiateHistoryDet
    assert hasattr(RecruitVacancyCandidiateHistoryDet, "VacancyAppliedHistoryID")
    assert hasattr(RecruitVacancyCandidiateHistoryDet, "VacancyCandidateID")


def test_job_profile_repository_fields_exist():
    # OrgJobProfileMst
    assert hasattr(OrgJobProfileMst, "JobProfileID")
    assert hasattr(OrgJobProfileMst, "JobProfileName")
    assert hasattr(OrgJobProfileMst, "JobProfileDesc")
    assert hasattr(OrgJobProfileMst, "CompID")
    assert hasattr(OrgJobProfileMst, "DeptID")
    assert hasattr(OrgJobProfileMst, "DesigID")
    assert hasattr(OrgJobProfileMst, "JobProfileIsActive")

    # OrgJobProfileQualificationDet
    assert hasattr(OrgJobProfileQualificationDet, "QualificationID")
    assert hasattr(OrgJobProfileQualificationDet, "JobProfileID")
    assert hasattr(OrgJobProfileQualificationDet, "QualificationIsDeleted")

    # JobProfileDomainKnowledgeDet
    assert hasattr(JobProfileDomainKnowledgeDet, "DomainKnowlgID")
    assert hasattr(JobProfileDomainKnowledgeDet, "JobProfileID")
    assert hasattr(JobProfileDomainKnowledgeDet, "JobProfileDomainKnowledgeDetIsActive")

    # String names and taxonomy
    assert hasattr(OrgLocationMst, "LocName")
    assert hasattr(LanguageMst, "LanguageDesc")
    assert hasattr(RecruitSkillMst, "SkillName")
    assert hasattr(RecruitDomainKnowledgeMst, "DomainKnowlgName")
    assert hasattr(QualificationMst, "QualificationName")
    assert hasattr(TransactionStatusMst, "StatusDesc")
    assert hasattr(OrgCompanyMst, "CompName")
    assert hasattr(OrgDepartmentMst, "DeptName")
    assert hasattr(OrgDesignationMst, "DesigName")


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
