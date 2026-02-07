from datetime import date
from enum import Enum

from sqlalchemy import (
    CHAR,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import declarative_base, relationship, validates

Base = declarative_base()


class Device(Enum):
    RPI_1 = "RPI-1"
    RPI_2 = "RPI-2"
    RPI_3 = "RPI-3"


class IEEERegistry(Enum):
    MA_L = "MA-L"
    MA_M = "MA-M"
    MA_S = "MA-S"


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
    # TODO Based on UAA IEEE lookup will be implemented later.
    uaa = Column(Boolean, nullable=True)

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
    timestamp = Column(DateTime, nullable=False)

    # __table_args__ = (
    #     UniqueConstraint(
    #         "ssid", "mac", "location", "timestamp", name="unique_captured"
    #     ),
    # )

    ssid_ref = relationship("SSID", back_populates="captures")
    mac_ref = relationship("MAC", back_populates="captures")
    location_ref = relationship("Location", back_populates="captures")


class LocationMapping(Base):
    __tablename__ = "location_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device = Column(String, unique=True, nullable=False)  # e.g., "RPI-1"
    location_id = Column(Integer, ForeignKey("location.id"), nullable=False)

    location = relationship("Location")


class DailyCapturedPerDevice(Base):
    __tablename__ = "daily_captured_per_device"
    __table_args__ = {"info": {"is_view": True}}

    # SQLAlchemy requires *some* primary key
    date = Column(Date, primary_key=True)
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
