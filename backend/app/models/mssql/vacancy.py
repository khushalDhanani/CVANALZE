from __future__ import annotations
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, Date, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import MssqlReadBase


class RecruitVacancyRequest(MssqlReadBase):
    __tablename__ = "RecruitVacancyRequest"
    __table_args__ = {"schema": "dbo"}

    VacancyRequestID = Column(BigInteger, primary_key=True)
    JobProfileID = Column(BigInteger, ForeignKey("dbo.OrgJobProfileMst.JobProfileID"))
    RequestTypeID = Column(BigInteger)
    NewTypeRemarks = Column(String)
    ReplaceByEmpID = Column(BigInteger)
    RequestForEmpID = Column(BigInteger)
    RequestPriorityID = Column(BigInteger)
    VacancyRequestIsPublic = Column(Boolean)
    RequestDate = Column(DateTime)
    RequestForCompID = Column(BigInteger, ForeignKey("dbo.OrgCompanyMst.CompID"))
    RequestForLocationID = Column(BigInteger, ForeignKey("dbo.OrgLocationMst.LocID"))
    RequestForMainDeptID = Column(BigInteger)
    RequestForDeptID = Column(BigInteger, ForeignKey("dbo.OrgDepartmentMst.DeptID"))
    PreferedGender = Column(String)
    RequestForDesigID = Column(BigInteger, ForeignKey("dbo.OrgDesignationMst.DesigID"))
    RequestedAdditionalKnowledge = Column(String)
    RequestedExperienceRangeFrom = Column(Numeric)
    RequestedExperienceRangeTo = Column(Numeric)
    RequestedCTCRangeFrom = Column(Numeric)
    RequestedCTCRangeTo = Column(Numeric)
    RequestedNoOfPosition = Column(Integer)
    RequestValidTillDate = Column(Date)
    RequestStatusID = Column(BigInteger, ForeignKey("dbo.TransactionStatusMst.StatusID"))
    RequestByEmpID = Column(BigInteger)
    VacancyRequestIsForceClosed = Column(Boolean)
    VacancyRequestForceClosedRemarks = Column(String)
    VacancyRequestClose = Column(Boolean)
    VacancyRequestCloseByEmpID = Column(BigInteger)
    VacancyRequestCloseDate = Column(DateTime)
    VacancyRequestIsActive = Column(Boolean)
    VacancyRequestIsDeleted = Column(Boolean)
    VacancyRequestEntDt = Column(DateTime)
    VacencyRequestEntUser = Column(String)
    VacencyRequestEntTerm = Column(String)
    VacencyRequestUpdDt = Column(DateTime)
    VacencyRequestUpdUser = Column(String)
    VacencyRequestUpdTerm = Column(String)
    VacencyRequestDelDt = Column(DateTime)
    VacencyRequestDelUser = Column(String)
    VacencyRequestDelTerm = Column(String)


class RecruitVacancyRequriedQualificationDet(MssqlReadBase):
    __tablename__ = "RecruitVacancyRequriedQualificationDet"
    __table_args__ = {"schema": "dbo"}

    RequiredID = Column(BigInteger, primary_key=True)
    VacancyRequestID = Column(BigInteger, ForeignKey("dbo.RecruitVacancyRequest.VacancyRequestID"))
    RequriedQualificationID = Column(BigInteger, ForeignKey("dbo.QualificationMst.QualificationID"))
    EntDt = Column(DateTime)
    EntUser = Column(String)
    EntTerm = Column(String)


class RecruitVacancyCandidateList(MssqlReadBase):
    __tablename__ = "RecruitVacancyCandidateList"
    __table_args__ = {"schema": "dbo"}

    VacancyCandidateID = Column(BigInteger, primary_key=True)
    VacancyRequestID = Column(BigInteger, ForeignKey("dbo.RecruitVacancyRequest.VacancyRequestID"))
    CandidateID = Column(BigInteger, ForeignKey("dbo.RecruitCandidateMst.CandidateID"))
    StatusID = Column(BigInteger, ForeignKey("dbo.TransactionStatusMst.StatusID"))
    HRRemarks = Column(String)
    HODRemarks = Column(String)
    TillHodingDate = Column(DateTime)
    VacancyCandidateIsActive = Column(Boolean)
    VacancyCandidateIsDeleted = Column(Boolean)
    VacancyCandidateEntDt = Column(DateTime)
    VacancyCandidateEntUser = Column(String)
    VacancyCandidateEntTerm = Column(String)
    VacancyCandidateUpdDt = Column(DateTime)
    VacancyCandidateUpdUser = Column(String)
    VacancyCandidateUpdTerm = Column(String)
    VacancyCandidateDelDt = Column(DateTime)
    VacancyCandidateDelUser = Column(String)
    VacancyCandidateDelTerm = Column(String)


class RecruitVacancyRequestTrack(MssqlReadBase):
    __tablename__ = "RecruitVacancyRequestTrack"
    __table_args__ = {"schema": "dbo"}

    VacancyTrackID = Column(BigInteger, primary_key=True)
    VacancyRequestID = Column(BigInteger, ForeignKey("dbo.RecruitVacancyRequest.VacancyRequestID"))
    VacancyReqByEmpID = Column(BigInteger)
    VacancyReqToEmpID = Column(BigInteger)
    VacancyReqStatusID = Column(BigInteger, ForeignKey("dbo.TransactionStatusMst.StatusID"))
    VacancyReqRemark = Column(String)
    VacancyReqIsDeleted = Column(Boolean)
    VacancyReqEntDt = Column(DateTime)
    VacancyReqEntUser = Column(String)
    VacancyReqEntTerm = Column(String)
    VacancyReqUpdDt = Column(DateTime)
    VacancyReqUpdUser = Column(String)
    VacancyReqUpdTerm = Column(String)
    VacancyReqDelDt = Column(DateTime)
    VacancyReqDelUser = Column(String)
    VacancyReqDelTerm = Column(String)


class RecruitVacancyCandidiateHistoryDet(MssqlReadBase):
    __tablename__ = "RecruitVacancyCandidiateHistoryDet"
    __table_args__ = {"schema": "dbo"}

    VacancyAppliedHistoryID = Column(BigInteger, primary_key=True)
    VacancyCandidateID = Column(BigInteger)
    StatusID = Column(BigInteger)
    StatusDT = Column(DateTime)
    EntDt = Column(DateTime)
    EntUser = Column(String)
    EntTerm = Column(String)
