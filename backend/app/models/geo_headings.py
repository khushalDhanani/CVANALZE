from datetime import UTC, datetime
from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.core.database import Base


class GeoLocation(Base):
    __tablename__ = "geo_locations"
    __table_args__ = {"schema": "cvai"}

    location_id = Column(Integer, primary_key=True, autoincrement=True)
    city_name = Column(String(255), nullable=False, index=True)
    state_name = Column(String(255), nullable=True)
    country_name = Column(String(255), default="Global")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class SectionHeading(Base):
    __tablename__ = "section_headings"
    __table_args__ = {"schema": "cvai"}

    heading_id = Column(Integer, primary_key=True, autoincrement=True)
    heading_text = Column(String(255), nullable=False, unique=True, index=True)
    category = Column(String(100), default="general")
    language = Column(String(10), default="en")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class NameDenylist(Base):
    __tablename__ = "name_denylists"
    __table_args__ = {"schema": "cvai"}

    denylist_id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(255), nullable=False, unique=True, index=True)
    category = Column(String(100), default="job_title")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
