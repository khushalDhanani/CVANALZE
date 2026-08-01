from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class OrgBusinessGroupMst(Base):
    __tablename__ = "OrgBusinessGroupMst"
    BusinessGrpID = Column(BigInteger, primary_key=True)
    BusinessGrpName = Column(String)
    BusinessGrpIsActive = Column(Boolean)
    
    companies = relationship("OrgCompanyMst", back_populates="business_group")

class OrgCompanyMst(Base):
    __tablename__ = "OrgCompanyMst"
    CompID = Column(BigInteger, primary_key=True)
    BusinessGrpID = Column(BigInteger, ForeignKey("OrgBusinessGroupMst.BusinessGrpID"))
    CompName = Column(String)
    CompIsActive = Column(Boolean)
    
    business_group = relationship("OrgBusinessGroupMst", back_populates="companies")
    departments = relationship("OrgDepartmentMst", back_populates="company")
    locations = relationship("OrgLocationMst", back_populates="company")

class OrgDepartmentMst(Base):
    __tablename__ = "OrgDepartmentMst"
    DeptID = Column(BigInteger, primary_key=True)
    CompID = Column(BigInteger, ForeignKey("OrgCompanyMst.CompID"))
    DeptName = Column(String)
    DeptIsActive = Column(Boolean)
    
    company = relationship("OrgCompanyMst", back_populates="departments")

class OrgLocationMst(Base):
    __tablename__ = "OrgLocationMst"
    LocID = Column(BigInteger, primary_key=True)
    CompID = Column(BigInteger, ForeignKey("OrgCompanyMst.CompID"))
    LocName = Column(String)
    LocAddress = Column(String)
    LocIsActive = Column(Boolean)
    
    company = relationship("OrgCompanyMst", back_populates="locations")

class OrgDesignationMst(Base):
    __tablename__ = "OrgDesignationMst"
    DesigID = Column(BigInteger, primary_key=True)
    CompID = Column(BigInteger, ForeignKey("OrgCompanyMst.CompID"))
    DeptID = Column(BigInteger, ForeignKey("OrgDepartmentMst.DeptID"))
    DesigName = Column(String)
    DesigIsActive = Column(Boolean)

class OrgJobProfileMst(Base):
    __tablename__ = "OrgJobProfileMst"
    JobProfileID = Column(BigInteger, primary_key=True)
    JobProfileName = Column(String)
    JobProfileDesc = Column(String)
    CompID = Column(BigInteger, ForeignKey("OrgCompanyMst.CompID"))
    DeptID = Column(BigInteger, ForeignKey("OrgDepartmentMst.DeptID"))
    DesigID = Column(BigInteger, ForeignKey("OrgDesignationMst.DesigID"))
    JobProfileIsActive = Column(Boolean)
