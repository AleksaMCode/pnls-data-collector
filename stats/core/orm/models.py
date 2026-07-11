from datetime import date
import uuid

from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, UUID
from sqlalchemy.orm import declarative_base, relationship

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

class TotalCapturedPerDevice(Base):
    __tablename__ = "total_captured_per_device"
    __table_args__ = {"info": {"is_view": True}}

    # SQLAlchemy requires a primary key for ORM-mapped views.
    device = Column(String, primary_key=True)
    ssid = Column(Integer, nullable=False)
    probe_request = Column(Integer, nullable=False)
    mac = Column(Integer, nullable=False)

class DailyCapturedPerDevice(Base):
    __tablename__ = "daily_captured_per_device"
    __table_args__ = {"info": {"is_view": True}}

    # SQLAlchemy requires *some* primary key
    date = Column(Date, primary_key=True)
    device = Column(String, primary_key=True)

    ssid = Column(Integer, nullable=False)
    probe_request = Column(Integer, nullable=False)
    mac = Column(Integer, nullable=False)

class ImportsInfo(Base):
    __tablename__ = "imports_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Date, nullable=False, default=date.today)
    captured = Column(Integer, nullable=False, default=0)
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("imports_workflow.id"),
        nullable=True,
        default=None,
    )
    workflow = relationship("ImportsWorkflow", back_populates="imports")


class ImportsWorkflow(Base):
    __tablename__ = "imports_workflow"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    imports = relationship("ImportsInfo", back_populates="workflow")