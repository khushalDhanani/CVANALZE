from __future__ import annotations
from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, String
from sqlalchemy.orm import relationship

from app.core.database import MssqlReadBase


class OrgBusinessGroupMst(MssqlReadBase):
    __tablename__ = "OrgBusinessGroupMst"

    __table_args__ = {"schema": "AIRIS"}

    BusinessGrpID = Column(BigInteger, primary_key=True)
    BusinessGrpName = Column(String)
    BusinessGrpIsActive = Column(Boolean)

    companies = relationship("OrgCompanyMst", back_populates="business_group")


class OrgCompanyMst(MssqlReadBase):
    __tablename__ = "OrgCompanyMst"

    __table_args__ = {"schema": "AIRIS"}

    CompID = Column(BigInteger, primary_key=True)
    BusinessGrpID = Column(BigInteger, ForeignKey("OrgBusinessGroupMst.BusinessGrpID"))
    CompName = Column(String)
    CompIsActive = Column(Boolean)

    business_group = relationship("OrgBusinessGroupMst", back_populates="companies")
    departments = relationship("OrgDepartmentMst", back_populates="company")
    locations = relationship("OrgLocationMst", back_populates="company")


class OrgDepartmentMst(MssqlReadBase):
    __tablename__ = "OrgDepartmentMst"

    __table_args__ = {"schema": "AIRIS"}

    DeptID = Column(BigInteger, primary_key=True)
    CompID = Column(BigInteger, ForeignKey("OrgCompanyMst.CompID"))
    DeptName = Column(String)
    DeptIsActive = Column(Boolean)

    company = relationship("OrgCompanyMst", back_populates="departments")


class OrgLocationMst(MssqlReadBase):
    __tablename__ = "OrgLocationMst"

    __table_args__ = {"schema": "AIRIS"}

    LocID = Column(BigInteger, primary_key=True)
    CompID = Column(BigInteger, ForeignKey("OrgCompanyMst.CompID"))
    LocName = Column(String)
    LocAddress = Column(String)
    LocIsActive = Column(Boolean)

    company = relationship("OrgCompanyMst", back_populates="locations")


class OrgDesignationMst(MssqlReadBase):
    __tablename__ = "OrgDesignationMst"

    __table_args__ = {"schema": "AIRIS"}

    DesigID = Column(BigInteger, primary_key=True)
    CompID = Column(BigInteger, ForeignKey("OrgCompanyMst.CompID"))
    DeptID = Column(BigInteger, ForeignKey("OrgDepartmentMst.DeptID"))
    DesigName = Column(String)
    DesigIsActive = Column(Boolean)


class OrgJobProfileMst(MssqlReadBase):
    __tablename__ = "OrgJobProfileMst"

    __table_args__ = {"schema": "AIRIS"}

    JobProfileID = Column(BigInteger, primary_key=True)
    JobProfileName = Column(String)
    JobProfileDesc = Column(String)
    CompID = Column(BigInteger, ForeignKey("OrgCompanyMst.CompID"))
    DeptID = Column(BigInteger, ForeignKey("OrgDepartmentMst.DeptID"))
    DesigID = Column(BigInteger, ForeignKey("OrgDesignationMst.DesigID"))
    JobProfileIsActive = Column(Boolean)

    qualifications = relationship("OrgJobProfileQualification")
    domains = relationship("OrgJobProfileDomain")

class OrgQualificationMst(MssqlReadBase):
    __tablename__ = "OrgQualificationMst"

    __table_args__ = {"schema": "AIRIS"}

    QualID = Column(BigInteger, primary_key=True)
    QualName = Column(String)
    QualIsActive = Column(Boolean)


class OrgDomainMst(MssqlReadBase):
    __tablename__ = "OrgDomainMst"

    __table_args__ = {"schema": "AIRIS"}

    DomainID = Column(BigInteger, primary_key=True)
    DomainName = Column(String)
    DomainIsActive = Column(Boolean)


class OrgJobProfileQualification(MssqlReadBase):
    __tablename__ = "OrgJobProfileQualification"

    __table_args__ = {"schema": "AIRIS"}

    JobProfileQualID = Column(BigInteger, primary_key=True)
    JobProfileID = Column(BigInteger, ForeignKey("OrgJobProfileMst.JobProfileID"))
    QualID = Column(BigInteger, ForeignKey("OrgQualificationMst.QualID"))
    IsMandatory = Column(Boolean, default=True)
    
    qualification = relationship("OrgQualificationMst")


class OrgJobProfileDomain(MssqlReadBase):
    __tablename__ = "OrgJobProfileDomain"

    __table_args__ = {"schema": "AIRIS"}

    JobProfileDomainID = Column(BigInteger, primary_key=True)
    JobProfileID = Column(BigInteger, ForeignKey("OrgJobProfileMst.JobProfileID"))
    DomainID = Column(BigInteger, ForeignKey("OrgDomainMst.DomainID"))
    IsMandatory = Column(Boolean, default=True)
    
    domain = relationship("OrgDomainMst")
