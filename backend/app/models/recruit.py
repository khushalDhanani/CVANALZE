from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Numeric, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class RecruitVacancyRequest(Base):
    __tablename__ = "RecruitVacancyRequest"

    VacancyRequestID = Column(BigInteger, primary_key=True)
    JobProfileID = Column(BigInteger, ForeignKey("OrgJobProfileMst.JobProfileID"))
    RequestForCompID = Column(BigInteger, ForeignKey("OrgCompanyMst.CompID"))
    RequestForDeptID = Column(BigInteger, ForeignKey("OrgDepartmentMst.DeptID"))
    RequestForLocationID = Column(BigInteger, ForeignKey("OrgLocationMst.LocID"))
    RequestForDesigID = Column(BigInteger, ForeignKey("OrgDesignationMst.DesigID"))

    RequestedExperienceRangeFrom = Column(Numeric(10, 2))
    RequestedExperienceRangeTo = Column(Numeric(10, 2))
    RequestedCTCRangeFrom = Column(Numeric(18, 2))
    RequestedCTCRangeTo = Column(Numeric(18, 2))
    RequestedAdditionalKnowledge = Column(String)
    PreferedGender = Column(String)

    VacancyRequestIsActive = Column(Boolean)
    VacancyRequestIsDeleted = Column(Boolean)
    VacancyRequestClose = Column(Boolean)
    VacancyRequestIsForceClosed = Column(Boolean)
    RequestStatusID = Column(BigInteger)

    # Relationships
    job_profile = relationship("OrgJobProfileMst")
    company = relationship("OrgCompanyMst")
    department = relationship("OrgDepartmentMst")
    location = relationship("OrgLocationMst")
    designation = relationship("OrgDesignationMst")


class RecruitCandidateMst(Base):
    __tablename__ = "RecruitCandidateMst"

    CandidateID = Column(BigInteger, primary_key=True)
    CandidateFirstName = Column(String)
    CandidateLastName = Column(String)
    CandidateJobProfileID = Column(BigInteger, ForeignKey("OrgJobProfileMst.JobProfileID"))

    CandidateCVFileName = Column(String)
    CandidateCVFileExtention = Column(String)

    CandidateTotExperience = Column(Numeric(10, 2))
    CandidateExpectedCtc = Column(Numeric(18, 2))
    CandidateIsActive = Column(Boolean)
    CandidateStatusID = Column(BigInteger)

    job_profile = relationship("OrgJobProfileMst")
