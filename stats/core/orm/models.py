from sqlalchemy import (
    Column,
    Float,
    Integer,
    String,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class CompanyCaptureSummary(Base):
    __tablename__ = "company_capture_summary"
    __table_args__ = {"info": {"is_view": True}}

    # SQLAlchemy requires a primary key for ORM-mapped views.
    company = Column(String, primary_key=True)
    country = Column(String, primary_key=True, nullable=True)
    country_alpha3 = Column(String(3), primary_key=True, nullable=True)
    total_occurrences = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)


class CompanyCaptureSummaryByDevice(Base):
    __tablename__ = "company_capture_summary_by_device"
    __table_args__ = {"info": {"is_view": True}}

    # SQLAlchemy requires a primary key for ORM-mapped views.
    device = Column(String, primary_key=True)
    company = Column(String, primary_key=True)
    country = Column(String, primary_key=True, nullable=True)
    country_alpha3 = Column(String(3), primary_key=True, nullable=True)
    total_occurrences = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)

class LocationMappingResolved(Base):
    __tablename__ = "location_mapping_resolved"
    __table_args__ = {"info": {"is_view": True}}

    # SQLAlchemy requires a primary key for ORM-mapped views.
    device = Column(String, primary_key=True)
    location = Column(String, nullable=False)
    coordinates = Column(String, nullable=True)
