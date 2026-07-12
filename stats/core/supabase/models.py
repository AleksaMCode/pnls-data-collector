from datetime import date as dt_date

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from stats.core.supabase._init_runtime import Base


class DailyImportsMac(Base):
    __tablename__ = "daily_imports_mac"
    __table_args__ = (UniqueConstraint("date", name="uq_daily_imports_mac_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    count = Column(BigInteger, nullable=False)
    date = Column(Date, nullable=False, index=True)


class DailyImportsSsid(Base):
    __tablename__ = "daily_imports_ssid"
    __table_args__ = (UniqueConstraint("date", name="uq_daily_imports_ssid_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    count = Column(BigInteger, nullable=False)
    date = Column(Date, nullable=False, index=True)


class DailyImportsProbes(Base):
    __tablename__ = "daily_imports_probes"
    __table_args__ = (UniqueConstraint("date", name="uq_daily_imports_probes_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    count = Column(BigInteger, nullable=False)
    date = Column(Date, nullable=False, index=True)


class Device(Base):
    __tablename__ = "devices"

    device = Column(String, primary_key=True)
    location = Column(String, nullable=False)
    coordinates = Column(String, nullable=True)


class DeviceDailyImports(Base):
    __tablename__ = "device_daily_imports"
    __table_args__ = (
        UniqueConstraint(
            "device_id", "date", name="uq_device_daily_imports_device_date"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, ForeignKey("devices.device"), nullable=False, index=True)
    ssid = Column(BigInteger, nullable=False)
    mac = Column(BigInteger, nullable=False)
    probes = Column(BigInteger, nullable=False)
    date = Column(Date, nullable=False, index=True)


class DeviceManufacturerStats(Base):
    __tablename__ = "device_manufacturer_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String, ForeignKey("devices.device"), nullable=False, index=True)
    manufacturer_data = Column(JSON, nullable=False)
    date = Column(Date, nullable=False, index=True, default=dt_date.today)


class ManufacturerStats(Base):
    __tablename__ = "manufacturer_stats"
    __table_args__ = (
        UniqueConstraint(
            "company",
            "country",
            "country_alpha3",
            name="uq_manufacturer_stats_company_country_alpha3",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    company = Column(String, nullable=False, index=True)
    country = Column(String, nullable=True)
    country_alpha3 = Column(String(3), nullable=True)
    total_occurrences = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)


class SsidStats(Base):
    __tablename__ = "ssid_stats"
    __table_args__ = (UniqueConstraint("ssid", name="uq_ssid_stats_ssid"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    ssid = Column(String, nullable=False, index=True)
    seen_count = Column(BigInteger, nullable=False)
    first_seen = Column(DateTime, nullable=False, index=True)
    last_seen = Column(DateTime, nullable=False, index=True)


class MacStats(Base):
    __tablename__ = "mac_stats"
    __table_args__ = (UniqueConstraint("mac", name="uq_mac_stats_mac"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    mac = Column(String, nullable=False)
    seen_count = Column(BigInteger, nullable=False)
    first_seen = Column(DateTime, nullable=False, index=True)
    last_seen = Column(DateTime, nullable=False, index=True)


class UniqueTotalStats(Base):
    __tablename__ = "unique_total_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    totals = Column(JSON, nullable=False)
    date = Column(Date, nullable=False, index=True)
