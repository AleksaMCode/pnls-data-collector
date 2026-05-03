from datetime import date
from enum import Enum

from sqlalchemy import (
    CHAR,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import declarative_base, relationship, validates

Base = declarative_base()


class IEEERegistry(Enum):
    MA_L = "MA-L"
    MA_M = "MA-M"
    MA_S = "MA-S"


IEEE_PRIORITY = (
    IEEERegistry.MA_S,
    IEEERegistry.MA_M,
    IEEERegistry.MA_L,
)


class SSID(Base):
    __tablename__ = "ssid"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ssid = Column(String(255), unique=True, nullable=False)

    captures = relationship("CapturedInfo", back_populates="ssid_ref")


class MAC(Base):
    __tablename__ = "mac"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mac = Column(String(17), unique=True, nullable=False)
    # Universally Administered MAC Address (UAA)
    uaa = Column(Boolean, nullable=True)
    oui = Column(Integer, ForeignKey("ieee_mac_oui.id"), nullable=True)

    captures = relationship("CapturedInfo", back_populates="mac_ref")

    @validates("mac")
    def _set_uaa(self, key, value):
        first_byte = int(value.split(":")[0], 16)
        self.uaa = (first_byte & 0x02) == 0
        return value


class Location(Base):
    __tablename__ = "location"

    id = Column(Integer, primary_key=True, autoincrement=True)
    location = Column(String(50), unique=True, nullable=False)
    description = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    captures = relationship("CapturedInfo", back_populates="location_ref")


class ImportsInfo(Base):
    __tablename__ = "imports_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Date, nullable=False, default=date.today)
    captured = Column(Integer, nullable=False, default=0)


class CapturedInfo(Base):
    __tablename__ = "captured_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ssid = Column(Integer, ForeignKey("ssid.id"), nullable=False)
    mac = Column(Integer, ForeignKey("mac.id"), nullable=False)
    location = Column(Integer, ForeignKey("location.id"), nullable=False)
    channel = Column(
        Integer, ForeignKey("channels_2_4_wifi.id"), nullable=False, default=10
    )
    timestamp = Column(DateTime, nullable=False)

    # __table_args__ = (
    #     UniqueConstraint(
    #         "ssid", "mac", "location", "timestamp", name="unique_captured"
    #     ),
    # )

    ssid_ref = relationship("SSID", back_populates="captures")
    mac_ref = relationship("MAC", back_populates="captures")
    location_ref = relationship("Location", back_populates="captures")


class Channels24Wifi(Base):
    __tablename__ = "channels_2_4_wifi"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_number = Column(Integer, nullable=False)
    lower_frequency = Column(Integer, nullable=False)
    center_frequency = Column(Integer, nullable=False)
    upper_frequency = Column(Integer, nullable=False)


class LocationMapping(Base):
    __tablename__ = "location_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device = Column(String, unique=True, nullable=False)  # e.g., "RPI-1"
    location_id = Column(Integer, ForeignKey("location.id"), nullable=False)

    location = relationship("Location")


class LocationMappingResolved(Base):
    __tablename__ = "location_mapping_resolved"
    __table_args__ = {"info": {"is_view": True}}

    # SQLAlchemy requires a primary key for ORM-mapped views.
    device = Column(String, primary_key=True)
    location = Column(String, nullable=False)
    coordinates = Column(String, nullable=True)


class DailyCapturedPerDevice(Base):
    __tablename__ = "daily_captured_per_device"
    __table_args__ = {"info": {"is_view": True}}

    # SQLAlchemy requires *some* primary key
    date = Column(Date, primary_key=True)
    device = Column(String, primary_key=True)

    ssid = Column(Integer, nullable=False)
    probe_request = Column(Integer, nullable=False)
    mac = Column(Integer, nullable=False)


class TotalCapturedPerDevice(Base):
    __tablename__ = "total_captured_per_device"
    __table_args__ = {"info": {"is_view": True}}

    # SQLAlchemy requires a primary key for ORM-mapped views.
    device = Column(String, primary_key=True)
    ssid = Column(Integer, nullable=False)
    probe_request = Column(Integer, nullable=False)
    mac = Column(Integer, nullable=False)


class Country(Base):
    __tablename__ = "country"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    alpha2 = Column(CHAR(2), unique=True, nullable=False)
    alpha3 = Column(CHAR(3), unique=True, nullable=False)
    country_code = Column(CHAR(3), unique=True, nullable=False)
    region = Column(String, nullable=True)
    sub_region = Column(String, nullable=True)
    intermediate_region = Column(String, nullable=True)
    region_code = Column(Integer, nullable=True)
    sub_region_code = Column(Integer, nullable=True)
    intermediate_region_code = Column(Integer, nullable=True)


class IEEEMacOuiOrg(Base):
    __tablename__ = "ieee_mac_oui_org"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    country = Column(Integer, ForeignKey("country.id"), nullable=True)


class IEEEMacOui(Base):
    __tablename__ = "ieee_mac_oui"

    id = Column(Integer, primary_key=True)
    registry = Column(String, nullable=False)
    assignment = Column(String, nullable=False)
    org = Column(Integer, ForeignKey("ieee_mac_oui_org.id"), nullable=False)


class IEEEMacOuiView(Base):
    __tablename__ = "ieee_mac_oui_with_country"

    id = Column(Integer, primary_key=True)
    registry = Column(String)
    assignment = Column(String)
    org = Column(String)
    # country not need for now, can be added later if needed
    # country = Column(String)


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
