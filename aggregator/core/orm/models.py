from datetime import date, datetime
from enum import Enum

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Device(Enum):
    RPI_1 = "RPI-1"
    RPI_2 = "RPI-2"
    RPI_3 = "RPI-3"


class SSID(Base):
    __tablename__ = "ssid"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ssid = Column(String(255), unique=True, nullable=False)

    captures = relationship("CapturedInfo", back_populates="ssid_ref")


class MAC(Base):
    __tablename__ = "mac"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mac = Column(String(17), unique=True, nullable=False)

    captures = relationship("CapturedInfo", back_populates="mac_ref")


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
