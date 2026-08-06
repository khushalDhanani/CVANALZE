from __future__ import annotations
from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, Date, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import MssqlReadBase


class OrgCompanyMst(MssqlReadBase):
    __tablename__ = "OrgCompanyMst"
    __table_args__ = {"schema": "dbo"}

    CompID = Column(BigInteger, primary_key=True)
    BusinessGrpID = Column(BigInteger, ForeignKey("dbo.OrgBusinessGroupMst.BusinessGrpID"))
    CompCode = Column(String)
    CompName = Column(String)
    CompAdd1 = Column(String)
    CompAdd2 = Column(String)
    CompAdd3 = Column(String)
    CompCityID = Column(BigInteger, ForeignKey("dbo.CityMst.CityID"))
    CompPinCode = Column(String)
    CompStateID = Column(BigInteger, ForeignKey("dbo.StateMst.StateID"))
    CompCountryID = Column(BigInteger, ForeignKey("dbo.CountryMst.CountryID"))
    CompWebURL = Column(String)
    CompEmail1 = Column(String)
    CompEmail2 = Column(String)
    CompPAN = Column(String)
    CompTDSNO = Column(String)
    CompPFNO = Column(String)
    CompESICNO = Column(String)
    CompEPTNO = Column(String)
    CompCPTNO = Column(String)
    CompTAN = Column(String)
    CompCINNo = Column(String)
    CompOccupierName = Column(String)
    CompNatureOfBiz = Column(String)
    CompIsActive = Column(Boolean)
    CompIsDeleted = Column(Boolean)
    CompRemark = Column(String)
    CompPFGroupCode = Column(String)
    CompFRNO = Column(String)
    CompNICCode = Column(String)
    CompLicenseDetail = Column(String)
    CompEntDt = Column(DateTime)
    CompEntUser = Column(String)
    CompEntTerm = Column(String)
    CompUpdDt = Column(DateTime)
    CompUpdTerm = Column(String)
    CompUpdUser = Column(String)
    CompDelTerm = Column(String)
    CompDelUser = Column(String)
    CompDelDt = Column(DateTime)
    CompContactNo = Column(String)
    CompEmerContactNo = Column(String)
    SAPCompCode = Column(BigInteger)
    CompPhoneNo = Column(String)


class OrgLocationMst(MssqlReadBase):
    __tablename__ = "OrgLocationMst"
    __table_args__ = {"schema": "dbo"}

    LocID = Column(BigInteger, primary_key=True)
    LocName = Column(String)
    OrgLocationTypeID = Column(BigInteger)
    LocAddress = Column(String)
    Loc_Latitude = Column(String)
    Loc_Longitude = Column(String)
    CompID = Column(BigInteger, ForeignKey("dbo.OrgCompanyMst.CompID"))
    LocIsActive = Column(Boolean)
    LocIsDeleted = Column(Boolean)
    LocEntDt = Column(DateTime)
    LocEntUser = Column(String)
    LocEntTerm = Column(String)
    LocUpdDt = Column(DateTime)
    LocUpdUser = Column(String)
    LocUpdTerm = Column(String)
    LocDelDt = Column(DateTime)
    LocDelUser = Column(String)
    LocDelTerm = Column(String)
    LocMapURL = Column(String)
    GoogleFormattedAddress = Column(String)
    ShortName = Column(String)
    StateID = Column(BigInteger)
    CountryID = Column(BigInteger)
    COSECLocID = Column(BigInteger)
    SOSSiteHeadEmpID = Column(BigInteger)
    SAPPlantCode = Column(BigInteger)
    CityID = Column(BigInteger)
    Ord = Column(BigInteger)
    LocCode = Column(String)
    CompPhoneNo = Column(String)
    IsAutoMation = Column(Boolean)
    BaseURL = Column(String)
    BaseIPAddress = Column(String)


class OrgMainDepartmentMst(MssqlReadBase):
    __tablename__ = "OrgMainDepartmentMst"
    __table_args__ = {"schema": "dbo"}

    MainDeptID = Column(BigInteger, primary_key=True)
    DeptName = Column(String)
    IsActive = Column(Boolean)
    EntDt = Column(DateTime)
    EntUser = Column(String)
    EntTerm = Column(String)
    UpdDt = Column(DateTime)
    UpdUser = Column(String)
    UpdTerm = Column(String)
    CosecMainDeptId = Column(BigInteger)


class OrgDepartmentMst(MssqlReadBase):
    __tablename__ = "OrgDepartmentMst"
    __table_args__ = {"schema": "dbo"}

    DeptID = Column(BigInteger, primary_key=True)
    CompID = Column(BigInteger, ForeignKey("dbo.OrgCompanyMst.CompID"))
    DeptName = Column(String)
    DeptHeadEmpID = Column(BigInteger)
    MainDeptID = Column(BigInteger)
    DeptIsActive = Column(Boolean)
    DeptIsDeleted = Column(Boolean)
    DeptEntDt = Column(DateTime)
    DeptEntUser = Column(String)
    DeptEntTerm = Column(String)
    DeptUpdDt = Column(DateTime)
    DeptUpdUser = Column(String)
    DeptUpdTerm = Column(String)
    DeptDelDt = Column(DateTime)
    DeptDelUser = Column(String)
    DeptDelTerm = Column(String)
    CosecDeptId = Column(BigInteger)
    SAPCostCenterCode = Column(BigInteger)
    SAPCostCenterCode_110 = Column(BigInteger)
    StreamID = Column(BigInteger)


class OrgDesignationMst(MssqlReadBase):
    __tablename__ = "OrgDesignationMst"
    __table_args__ = {"schema": "dbo"}

    DesigID = Column(BigInteger, primary_key=True)
    CompID = Column(BigInteger, ForeignKey("dbo.OrgCompanyMst.CompID"))
    DeptID = Column(BigInteger, ForeignKey("dbo.OrgDepartmentMst.DeptID"))
    MainDeptID = Column(BigInteger)
    DesigName = Column(String)
    DesigOrd = Column(Numeric)
    DesigType = Column(String)
    DesigIsHR = Column(Boolean)
    DesigIsAccount = Column(Boolean)
    DesigIsActive = Column(Boolean)
    DesigIsManager = Column(Boolean)
    DesigIsLWF = Column(Boolean)
    DesigIsCntManager = Column(Boolean)
    DesigIsMatrixRuleAllow = Column(Boolean)
    DesigIsDeleted = Column(Boolean)
    EmpGradeID = Column(BigInteger)
    DesigEntDt = Column(DateTime)
    DesigEntUser = Column(String)
    DesigEntTerm = Column(String)
    DesigUpdDt = Column(DateTime)
    DesigUpdUser = Column(String)
    DesigUpdTerm = Column(String)
    DesigDelDt = Column(DateTime)
    DesigDelUser = Column(String)
    DesigDelTerm = Column(String)
    CosecDesigID = Column(BigInteger)
    StreamID = Column(BigInteger)
    EmpType = Column(String)
    IsAllowForReporting = Column(Boolean)


class OrgJobProfileMst(MssqlReadBase):
    __tablename__ = "OrgJobProfileMst"
    __table_args__ = {"schema": "dbo"}

    JobProfileID = Column(BigInteger, primary_key=True)
    JobProfileName = Column(String)
    JobProfileDesc = Column(String)
    MainDeptID = Column(BigInteger)
    DeptID = Column(BigInteger, ForeignKey("dbo.OrgDepartmentMst.DeptID"))
    DomainKnowlgID = Column(BigInteger, ForeignKey("dbo.RecruitDomainKnowledgeMst.DomainKnowlgID"))
    CompID = Column(BigInteger, ForeignKey("dbo.OrgCompanyMst.CompID"))
    DesigID = Column(BigInteger, ForeignKey("dbo.OrgDesignationMst.DesigID"))
    JobProfileFileName = Column(String)
    JobProfileFileExtention = Column(String)
    JobProfileIsActive = Column(Boolean)
    JobProfileIsDeleted = Column(Boolean)
    JobProfileEntDt = Column(DateTime)
    JobProfileEntUser = Column(String)
    JobProfileEntTerm = Column(String)
    JobProfileUpdDt = Column(DateTime)
    JobProfileUpdUser = Column(String)
    JobProfileUpdTerm = Column(String)
    JobProfileDelDt = Column(DateTime)
    JobProfileDelUser = Column(String)
    JobProfileDelTerm = Column(String)


class JobProfileDomainKnowledgeDet(MssqlReadBase):
    __tablename__ = "JobProfileDomainKnowledgeDet"
    __table_args__ = {"schema": "dbo"}

    JobProfileDomainKnowledgeDetID = Column(BigInteger, primary_key=True)
    JobProfileID = Column(BigInteger, ForeignKey("dbo.OrgJobProfileMst.JobProfileID"))
    DomainKnowlgID = Column(BigInteger, ForeignKey("dbo.RecruitDomainKnowledgeMst.DomainKnowlgID"))
    JobProfileDomainKnowledgeDetIsActive = Column(Boolean)
    JobProfileDomainKnowledgeDetEntDt = Column(DateTime)
    JobProfileDomainKnowledgeDetEntUser = Column(String)
    JobProfileDomainKnowledgeDetEntTerm = Column(String)
    JobProfileDomainKnowledgeDetUpdDt = Column(DateTime)
    JobProfileDomainKnowledgeDetUpdUser = Column(String)
    JobProfileDomainKnowledgeDetUpdTerm = Column(String)


class OrgJobProfileQualificationDet(MssqlReadBase):
    __tablename__ = "OrgJobProfileQualificationDet"
    __table_args__ = {"schema": "dbo"}

    JobProfileQualificationDetID = Column(BigInteger, primary_key=True)
    JobProfileID = Column(BigInteger, ForeignKey("dbo.OrgJobProfileMst.JobProfileID"))
    QualificationID = Column(BigInteger, ForeignKey("dbo.QualificationMst.QualificationID"))
    QualificationIsDeleted = Column(Boolean)
    JobProfileQualificationEntDt = Column(DateTime)
    JobProfileQualificationEntUser = Column(String)
    JobProfileQualificationEntTerm = Column(String)
    JobProfileQualificationUpdDt = Column(DateTime)
    JobProfileQualificationUpdUser = Column(String)
    JobProfileQualificationUpdTerm = Column(String)
    JobProfileQualificationDelDt = Column(DateTime)
    JobProfileQualificationDelUser = Column(String)
    JobProfileQualificationDelTerm = Column(String)


class OrgDesignationMappingDet(MssqlReadBase):
    __tablename__ = "OrgDesignationMappingDet"
    __table_args__ = {"schema": "dbo"}

    OrgDesigMapID = Column(BigInteger, primary_key=True)
    OrgDesigIDAether = Column(BigInteger, ForeignKey("dbo.OrgDesignationMstAether.DesigID"))
    OrgDesigID = Column(BigInteger, ForeignKey("dbo.OrgDesignationMst.DesigID"))


class JobProfileDepartmentDet(MssqlReadBase):
    __tablename__ = "JobProfileDepartmentDet"
    __table_args__ = {"schema": "dbo"}

    JobProfileDepartmentDetID = Column(BigInteger, primary_key=True)
    JobProfileID = Column(BigInteger, ForeignKey("dbo.OrgJobProfileMst.JobProfileID"))
    DeptID = Column(BigInteger, ForeignKey("dbo.OrgDepartmentMst.DeptID"))
    JobProfileDepartmentDetIsActive = Column(Boolean)
    JobProfileDepartmentDetEntDt = Column(DateTime)
    JobProfileDepartmentDetEntUser = Column(String)
    JobProfileDepartmentDetEntTerm = Column(String)
    JobProfileDepartmentDetUpdDt = Column(DateTime)
    JobProfileDepartmentDetUpdUser = Column(String)
    JobProfileDepartmentDetUpdTerm = Column(String)
