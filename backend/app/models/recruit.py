from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Numeric, String
from sqlalchemy.orm import relationship

from app.core.database import MssqlReadBase


class RecruitVacancyRequest(MssqlReadBase):
    __tablename__ = "RecruitVacancyRequest"

    __table_args__ = {"schema": "AIRIS"}
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

    qualifications = relationship("RecruitVacancyQualification")
    domains = relationship("RecruitVacancyDomain")


class RecruitCandidateMst(MssqlReadBase):
    __tablename__ = "RecruitCandidateMst"

    __table_args__ = {"schema": "AIRIS"}
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

    qualifications = relationship("RecruitCandidateQualification")
    domains = relationship("RecruitCandidateDomain")
    workflow_states = relationship("RecruitWorkflowState")


class RecruitSkillMst(MssqlReadBase):
    __tablename__ = "RecruitSkillMst"

    __table_args__ = {"schema": "AIRIS"}
    SkillID = Column(BigInteger, primary_key=True)
    SkillTypeID = Column(BigInteger)
    SkillName = Column(String(255), nullable=False)
    SkillDesc = Column(String(500), nullable=True)
    SkillIsActive = Column(Boolean, default=True)


class RecruitWorkflowMst(MssqlReadBase):
    __tablename__ = "RecruitWorkflowMst"

    __table_args__ = {"schema": "AIRIS"}    WorkflowID = Column(BigInteger, primary_key=True)
    WorkflowName = Column(String)


class RecruitCandidateQualification(MssqlReadBase):
    __tablename__ = "RecruitCandidateQualification"

    __table_args__ = {"schema": "AIRIS"}    CandQualID = Column(BigInteger, primary_key=True)
    CandidateID = Column(BigInteger, ForeignKey("RecruitCandidateMst.CandidateID"))
    QualID = Column(BigInteger, ForeignKey("OrgQualificationMst.QualID"))


class RecruitCandidateDomain(MssqlReadBase):
    __tablename__ = "RecruitCandidateDomain"

    __table_args__ = {"schema": "AIRIS"}    CandDomainID = Column(BigInteger, primary_key=True)
    CandidateID = Column(BigInteger, ForeignKey("RecruitCandidateMst.CandidateID"))
    DomainID = Column(BigInteger, ForeignKey("OrgDomainMst.DomainID"))


class RecruitVacancyQualification(MssqlReadBase):
    __tablename__ = "RecruitVacancyQualification"

    __table_args__ = {"schema": "AIRIS"}    VacancyQualID = Column(BigInteger, primary_key=True)
    VacancyRequestID = Column(BigInteger, ForeignKey("RecruitVacancyRequest.VacancyRequestID"))
    QualID = Column(BigInteger, ForeignKey("OrgQualificationMst.QualID"))


class RecruitVacancyDomain(MssqlReadBase):
    __tablename__ = "RecruitVacancyDomain"

    __table_args__ = {"schema": "AIRIS"}    VacancyDomainID = Column(BigInteger, primary_key=True)
    VacancyRequestID = Column(BigInteger, ForeignKey("RecruitVacancyRequest.VacancyRequestID"))
    DomainID = Column(BigInteger, ForeignKey("OrgDomainMst.DomainID"))


class RecruitWorkflowState(MssqlReadBase):
    __tablename__ = "RecruitWorkflowState"

    __table_args__ = {"schema": "AIRIS"}    StateID = Column(BigInteger, primary_key=True)
    CandidateID = Column(BigInteger, ForeignKey("RecruitCandidateMst.CandidateID"))
    VacancyRequestID = Column(BigInteger, ForeignKey("RecruitVacancyRequest.VacancyRequestID"))
    WorkflowID = Column(BigInteger, ForeignKey("RecruitWorkflowMst.WorkflowID"))
    CurrentState = Column(String)

