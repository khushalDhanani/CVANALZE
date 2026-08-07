from __future__ import annotations
from sqlalchemy import Column, String, BigInteger, Boolean, DateTime, Numeric, ForeignKey
from app.core.database import MssqlReadBase


class RecruitDomainKnowledgeMst(MssqlReadBase):
    __tablename__ = "RecruitDomainKnowledgeMst"
    __table_args__ = {"schema": "dbo"}

    DomainKnowlgID = Column(BigInteger, primary_key=True)
    DomainKnowlgName = Column(String)
    DomainKnowlgIsActive = Column(Boolean)
    DomainKnowlgIsDeleted = Column(Boolean)
    DomainKnowlgEntDt = Column(DateTime)
    DomainKnowlgEntUser = Column(String)
    DomainKnowlgEntTerm = Column(String)
    DomainKnowlgUpdDt = Column(DateTime)
    DomainKnowlgUpdUser = Column(String)
    DomainKnowlgUpdTerm = Column(String)
    DomainKnowlgDelDt = Column(DateTime)
    DomainKnowlgDelUser = Column(String)
    DomainKnowlgDelTerm = Column(String)


class RecruitDomainKnowledgeDeptDet(MssqlReadBase):
    __tablename__ = "RecruitDomainKnowledgeDeptDet"
    __table_args__ = {"schema": "dbo"}

    DomainKnowlgDeptDetID = Column(BigInteger, primary_key=True)
    DomainKnowlgID = Column(BigInteger, ForeignKey("dbo.RecruitDomainKnowledgeMst.DomainKnowlgID"))
    DeptID = Column(BigInteger, ForeignKey("dbo.OrgDepartmentMst.DeptID"))
    IsActive = Column(Boolean)
    EntDt = Column(DateTime)
    EntUser = Column(String)
    EntTerm = Column(String)
    UpdDt = Column(DateTime)
    UpdUser = Column(String)
    UpdTerm = Column(String)


class RecruitDomainKnowledgeSkillDet(MssqlReadBase):
    __tablename__ = "RecruitDomainKnowledgeSkillDet"
    __table_args__ = {"schema": "dbo"}

    DomainKnowlgSkillDetID = Column(BigInteger, primary_key=True)
    DomainKnowlgID = Column(BigInteger, ForeignKey("dbo.RecruitDomainKnowledgeMst.DomainKnowlgID"))
    SkillID = Column(BigInteger, ForeignKey("dbo.RecruitSkillMst.SkillID"))
    IsActive = Column(Boolean)
    EntDt = Column(DateTime)
    EntUser = Column(String)
    EntTerm = Column(String)
    UpdDt = Column(DateTime)
    UpdUser = Column(String)
    UpdTerm = Column(String)


class RecruitSkillMst(MssqlReadBase):
    __tablename__ = "RecruitSkillMst"
    __table_args__ = {"schema": "dbo"}

    SkillID = Column(BigInteger, primary_key=True)
    SkillTypeID = Column(BigInteger, ForeignKey("dbo.RecruitSkillTypeMst.SkillTypeID"))
    SkillName = Column(String)
    SkillDesc = Column(String)
    ApplicableToAll = Column(Boolean)
    SkillIsActive = Column(Boolean)
    EntDt = Column(DateTime)
    EntUser = Column(String)
    EntTerm = Column(String)
    UpdDt = Column(DateTime)
    UpdUser = Column(String)
    UpdTerm = Column(String)


class RecruitSkillTypeMst(MssqlReadBase):
    __tablename__ = "RecruitSkillTypeMst"
    __table_args__ = {"schema": "dbo"}

    SkillTypeID = Column(BigInteger, primary_key=True)
    SkillTypeName = Column(String)
    SkillTypeIsActive = Column(Boolean)
    EntDt = Column(DateTime)
    EntUser = Column(String)
    EntTerm = Column(String)
    UpdDt = Column(DateTime)
    UpdUser = Column(String)
    UpdTerm = Column(String)


class QualificationMst(MssqlReadBase):
    __tablename__ = "QualificationMst"
    __table_args__ = {"schema": "dbo"}

    QualificationID = Column(BigInteger, primary_key=True)
    QualificationName = Column(String)
    QualificationIsActive = Column(Boolean)
    QualificationIsDeleted = Column(Boolean)
    QualificationEntDt = Column(DateTime)
    QualificationEntUser = Column(String)
    QualificationEntTerm = Column(String)
    QualificationUpdDt = Column(DateTime)
    QualificationUpdUser = Column(String)
    QualificationUpdTerm = Column(String)
    QualificationDelDt = Column(DateTime)
    QualificationDelUser = Column(String)
    QualificationDelTerm = Column(String)


class TransactionStatusMst(MssqlReadBase):
    __tablename__ = "TransactionStatusMst"
    __table_args__ = {"schema": "dbo"}

    StatusID = Column(BigInteger, primary_key=True)
    StatusDesc = Column(String)
    ModuleName = Column(String)
    TransactionStatus = Column(String)
    StatusIsActive = Column(Boolean)
    StatusIsDeleted = Column(Boolean)
    StatusEntDt = Column(DateTime)
    StatusEntUser = Column(String)
    StatusEntTerm = Column(String)
    StatusUpdDt = Column(DateTime)
    StatusUpdUser = Column(String)
    StatusUpdTerm = Column(String)
    StatusDelDt = Column(DateTime)
    StatusDelUser = Column(String)
    StatusDelTerm = Column(String)
    ReservedKeywords = Column(String)
    StatusIcon = Column(String)
    StatusColor = Column(String)
    IsAction = Column(Boolean)
    ShowText = Column(Boolean)
    ActionName = Column(String)
    ActionIcon = Column(String)
    ActionColor = Column(String)
    StatusValue = Column(BigInteger)
    StatusMasking = Column(String)
    Ord = Column(BigInteger)
    TransCatID = Column(BigInteger)


class LanguageMst(MssqlReadBase):
    __tablename__ = "LanguageMst"
    __table_args__ = {"schema": "dbo"}

    LanguageID = Column(BigInteger, primary_key=True)
    LanguageDesc = Column(String)
    LanguageIsActive = Column(Boolean)
    LanguageIsDeleted = Column(Boolean)
    LanguageEntDt = Column(DateTime)
    LanguageEntUser = Column(String)
    LanguageEntTerm = Column(String)
    LanguageUpdDt = Column(DateTime)
    LanguageUpdUser = Column(String)
    LanguageUpdTerm = Column(String)
    LanguageDelDt = Column(DateTime)
    LanguageDelUser = Column(String)
    LanugageDelTerm = Column(String)


class CityMst(MssqlReadBase):
    __tablename__ = "CityMst"
    __table_args__ = {"schema": "dbo"}

    CityID = Column(BigInteger, primary_key=True)
    CityName = Column(String)
    StateID = Column(BigInteger, ForeignKey("dbo.StateMst.StateID"))
    Latitude = Column(Numeric)
    Longitude = Column(Numeric)
    CityGradeID = Column(BigInteger, ForeignKey("dbo.CityGradeMst.CityGradeID"))
    CityIsActive = Column(Boolean)
    CityIsDelted = Column(Boolean)
    CityEntDt = Column(DateTime)
    CityEntUser = Column(String)
    CityEntTerm = Column(String)
    CityUpdDt = Column(DateTime)
    CityUpdUser = Column(String)
    CityUpdTerm = Column(String)
    CityDelDt = Column(DateTime)
    CityDelUser = Column(String)
    CityDelTerm = Column(String)


class StateMst(MssqlReadBase):
    __tablename__ = "StateMst"
    __table_args__ = {"schema": "dbo"}

    StateID = Column(BigInteger, primary_key=True)
    StateName = Column(String)
    CountryID = Column(BigInteger, ForeignKey("dbo.CountryMst.CountryID"))
    StateIsActive = Column(Boolean)
    StateIsDeleted = Column(Boolean)
    Latitude = Column(Numeric)
    Longitude = Column(Numeric)
    StateEntDt = Column(DateTime)
    StateEntUser = Column(String)
    StateEntTerm = Column(String)
    StateUpdDt = Column(DateTime)
    StateUpdUser = Column(String)
    StateUpdTerm = Column(String)
    StateDelDt = Column(DateTime)
    StateDelUser = Column(String)
    StateDelTerm = Column(String)


class CountryMst(MssqlReadBase):
    __tablename__ = "CountryMst"
    __table_args__ = {"schema": "dbo"}

    CountryID = Column(BigInteger, primary_key=True)
    CountryName = Column(String)
    RegionID = Column(BigInteger)
    Latitude = Column(Numeric)
    Longitude = Column(Numeric)
    Currency = Column(String)
    ISOName = Column(String)
    Nationality = Column(String)
    Capital = Column(String)
    TimeZone = Column(String)
    PhoneCode = Column(String)
    CountryIsActive = Column(Boolean)
    CountryIsDeleted = Column(Boolean)
    CountryEntDt = Column(DateTime)
    CountryEntUser = Column(String)
    CountryEntTerm = Column(String)
    CountryUpdDt = Column(DateTime)
    CountryUpdUser = Column(String)
    CountryUpdTerm = Column(String)
    CountryDelDt = Column(DateTime)
    CountryDelUser = Column(String)
    CountryDelTerm = Column(String)


class OrgBusinessGroupMst(MssqlReadBase):
    __tablename__ = "OrgBusinessGroupMst"
    __table_args__ = {"schema": "dbo"}

    BusinessGrpID = Column(BigInteger, primary_key=True)
    BusinessGrpName = Column(String)
    BusinessGrpIsActive = Column(Boolean)
    BusinessGrpIsDeleted = Column(Boolean)
    BusinessGrpRemark = Column(String)
    BusinessGrpEntDt = Column(DateTime)
    BusinessGrpEntUser = Column(String)
    BusinessGrpEntTerm = Column(String)
    BusinessGrpUpdDt = Column(DateTime)
    BusinessGrpUpdTerm = Column(String)
    BusinessGrpUpdUser = Column(String)
    BusinessGrpDelTerm = Column(String)
    BusinessGrpDelUser = Column(String)
    BusinessGrpDelDt = Column(DateTime)


class OrgDesignationMstAether(MssqlReadBase):
    __tablename__ = "OrgDesignationMstAether"
    __table_args__ = {"schema": "dbo"}

    DesigID = Column(BigInteger, primary_key=True)
    CompID = Column(BigInteger)
    DesigName = Column(String)
    DesigOrd = Column(Numeric)
    DesigType = Column(String)
    DesigIsHR = Column(Boolean)
    DesigIsAccount = Column(Boolean)
    DesigIsActive = Column(Boolean)
    DesigIsManager = Column(Boolean)
    DesigIsLWF = Column(Boolean)
    DesigIsDeleted = Column(Boolean)
    DesigColorCode = Column(String)
    DesigEntDt = Column(DateTime)
    DesigEntUser = Column(String)
    DesigEntTerm = Column(String)
    DesigUpdDt = Column(DateTime)
    DesigUpdUser = Column(String)
    DesigUpdTerm = Column(String)
    DesigDelDt = Column(DateTime)
    DesigDelUser = Column(String)
    DesigDelTerm = Column(String)


class EmployeeGradeMst(MssqlReadBase):
    __tablename__ = "EmployeeGradeMst"
    __table_args__ = {"schema": "dbo"}

    EmpGradeID = Column(BigInteger, primary_key=True)
    EmpGradeDesc = Column(String)
    EmpGradeRemark = Column(String)
    EmpGradeIsActive = Column(Boolean)
    EmpGradeIsDeleted = Column(Boolean)
    EmpGradeEntDt = Column(DateTime)
    EmpGradeEntUser = Column(String)
    EmpGradeEntTerm = Column(String)
    EmpGradeUpdDt = Column(DateTime)
    EmpGradeUpdUser = Column(String)
    EmpGradeUpdTerm = Column(String)
    EmpGradeDelDt = Column(DateTime)
    EmpGradeDelUser = Column(String)
    EmpGradeDelTerm = Column(String)
    EmpGradeColor = Column(String)
    CosecGradeID = Column(BigInteger)
    NoticePeriodDays = Column(BigInteger)


class RecruitChannelMst(MssqlReadBase):
    __tablename__ = "RecruitChannelMst"
    __table_args__ = {"schema": "dbo"}

    RecruitChannelID = Column(BigInteger, primary_key=True)
    RecruitChannelCategoryID = Column(BigInteger, ForeignKey("dbo.RecruitChannelCategoryMst.RecruitChannelCategoryID"))
    RecruitChannelName = Column(String)
    RecruitChannelContactPerson = Column(String)
    RecruitChannelCountryID = Column(BigInteger)
    RecruitChannelStateID = Column(BigInteger)
    RecruitChannelCityID = Column(BigInteger)
    RecruitChannelPincode = Column(BigInteger)
    RecruitChannelPanNo = Column(String)
    RecruitChannelGSTNo = Column(String)
    RecruitChannelAdd1 = Column(String)
    RecruitChannelAdd2 = Column(String)
    RecruitChannelAdd3 = Column(String)
    RecruitChannelPhone1 = Column(String)
    RecruitChannelPhone2 = Column(String)
    RecruitChannelFax = Column(String)
    RecruitChannelEmailID = Column(String)
    RecruitChannelCommissionPer = Column(Numeric)
    RecruitChannelRemark = Column(String)
    RecruitChannelContractValidFrom = Column(DateTime)
    RecruitChannelContractValidTo = Column(DateTime)
    RecruitChannelContractExtendDaysAlert = Column(BigInteger)
    RecruitChannelAetherAgreementFile = Column(String)
    RecruitChannelChannelAgreementFile = Column(String)
    RecruitChannelIsActive = Column(Boolean)
    RecruitChannelIsDeleted = Column(Boolean)
    RecruitChannelEntDt = Column(DateTime)
    RecruitChannelEntUser = Column(String)
    RecruitChannelEntTerm = Column(String)
    RecruitChannelUpdDt = Column(DateTime)
    RecuritChannelUpdUser = Column(String)
    RecruitChannelUpdTerm = Column(String)
    RecuritChannelDelDt = Column(DateTime)
    RecruitChannelDelUser = Column(String)
    RecruitChannelDelTerm = Column(String)


class RecruitChannelCategoryMst(MssqlReadBase):
    __tablename__ = "RecruitChannelCategoryMst"
    __table_args__ = {"schema": "dbo"}

    RecruitChannelCategoryID = Column(BigInteger, primary_key=True)
    RecruitChannelCategoryName = Column(String)
    RecruitChannelCategoryIsActive = Column(Boolean)
    RecruitChannelCategoryIsDeleted = Column(Boolean)
    RecruitChannelCategoryEntDt = Column(DateTime)
    RecruitChannelCategoryEntUser = Column(String)
    RecruitChannelCategoryEntTerm = Column(String)
    RecruitChannelCategoryUpdDt = Column(DateTime)
    RecruitChannelCategoryUpdUser = Column(String)
    RecruitChannelCategoryUpdTerm = Column(String)
    RecruitChannelCategoryDelDt = Column(DateTime)
    RecruitChannelCategoryDelUser = Column(String)
    RecruitChannelCategoryDelTerm = Column(String)
